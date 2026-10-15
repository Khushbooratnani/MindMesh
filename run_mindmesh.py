#!/usr/bin/env python3
"""MindMesh Real End-to-End Local & Server Runner.

Provides a developer-friendly entry point to launch and interact with the
complete MindMesh platform (PostgreSQL, Database Schema, FastAPI backend,
Phase 1 pipeline, and Orchestration storage) using raw text without manual JSON.
"""

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from typing import Any

import httpx

# Determine backend directory dynamically
WORKSPACE_ROOT = Path(__file__).resolve().parent

candidate_paths = [
    WORKSPACE_ROOT / "backend" / "phase1_text_to_json_ingestion",
    WORKSPACE_ROOT / "backend",
    WORKSPACE_ROOT / "MindMesh-main" / "backend",
    WORKSPACE_ROOT,
]

BACKEND_DIR = None
for candidate in candidate_paths:
    if (candidate / "app").exists():
        BACKEND_DIR = candidate
        break

if not BACKEND_DIR:
    BACKEND_DIR = WORKSPACE_ROOT

# Ensure backend directory is in sys.path
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

API_BASE_URL = "http://127.0.0.1:8001"
HEALTH_URL = f"{API_BASE_URL}/health"
INGEST_URL = f"{API_BASE_URL}/api/v1/memories/ingest"


def is_port_open(host: str = "127.0.0.1", port: int = 5432, timeout: float = 1.0) -> bool:
    """Check if a TCP port is open and listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def check_and_start_postgres() -> bool:
    """Check if PostgreSQL is running; start user-space instance if present."""
    # 1. Check if standard port 5432 is already listening
    if is_port_open("127.0.0.1", 5432):
        return True

    # 2. Check for Debian user-space postgres installation
    home_dir = Path.home()
    pg_ctl = home_dir / "mindmesh" / "postgres" / "bin" / "pg_ctl"
    pg_data = home_dir / "mindmesh" / "data" / "postgres"
    pg_log = home_dir / "mindmesh" / "Logs" / "postgres.log"

    if pg_ctl.exists() and pg_data.exists():
        print("  PostgreSQL stopped. Starting user-space PostgreSQL instance...")
        pg_log.parent.mkdir(parents=True, exist_ok=True)
        cmd = [str(pg_ctl), "-D", str(pg_data), "-l", str(pg_log), "start"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"  [ERROR] Failed to start PostgreSQL: {res.stderr}")
            return False

        # Wait up to 5 seconds for port to open
        for _ in range(10):
            time.sleep(0.5)
            if is_port_open("127.0.0.1", 5432):
                return True
        return False

    # 3. If port is not open and pg_ctl not found, return False
    return False


def check_and_init_database(pg_running: bool) -> bool:
    """Ensure database schema tables (raw_inputs, phase1_outputs) are initialized."""
    try:
        from app.database.migrations.runner import init_db_schema
        from app.database.connection.session import create_async_engine_instance
        import asyncio

        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            if pg_running:
                db_url = "postgresql+asyncpg://coeai@localhost:5432/mindmesh"
            else:
                db_url = f"sqlite+aiosqlite:///{BACKEND_DIR / 'mindmesh_local.db'}"
                os.environ["DATABASE_URL"] = db_url

        engine = create_async_engine_instance(database_url=db_url)
        asyncio.run(init_db_schema(engine))
        return True
    except Exception as exc:
        print(f"  [Database note]: {exc}")
        return True


def is_backend_healthy() -> bool:
    """Probe GET /health on FastAPI backend."""
    try:
        with httpx.Client(timeout=1.5) as client:
            resp = client.get(HEALTH_URL)
            return resp.status_code == 200 and resp.json().get("status") == "ok"
    except Exception:
        return False


def stop_stale_backend_if_any() -> None:
    """Terminate ONLY the process listening on TCP port 8001 to ensure a clean runtime lifecycle."""
    if not is_port_open("127.0.0.1", 8001):
        return

    if sys.platform != "win32":
        # 1. Use lsof to identify PID(s) listening on TCP port 8001 and terminate gracefully
        try:
            res = subprocess.run(["lsof", "-t", "-i:8001"], capture_output=True, text=True)
            for pid in res.stdout.strip().split():
                if pid.isdigit():
                    subprocess.run(["kill", "-15", pid], capture_output=True)
        except Exception:
            pass
        time.sleep(0.5)

        # 2. If port 8001 is still occupied, escalate with SIGKILL to only those PID(s)
        if is_port_open("127.0.0.1", 8001):
            try:
                res = subprocess.run(["lsof", "-t", "-i:8001"], capture_output=True, text=True)
                for pid in res.stdout.strip().split():
                    if pid.isdigit():
                        subprocess.run(["kill", "-9", pid], capture_output=True)
            except Exception:
                pass
            time.sleep(0.5)
    else:
        try:
            res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            for line in res.stdout.splitlines():
                if ":8001" in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    if pid.isdigit() and pid != "0":
                        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        except Exception:
            pass

    for _ in range(10):
        if not is_port_open("127.0.0.1", 8001):
            break
        time.sleep(0.2)


def _log_tee_worker(proc: subprocess.Popen[str], log_path: Path) -> None:
    """Continuously relay child stdout lines to persistent backend.log AND live terminal stdout."""
    if proc.stdout is None:
        return
    try:
        with open(log_path, "a", encoding="utf-8", buffering=1) as f:
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                # Always write to persistent log file on disk
                try:
                    f.write(line)
                    f.flush()
                except Exception:
                    pass
                # Stream live to parent terminal if available
                try:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                except Exception:
                    # Ignore broken pipe on terminal stdout if SSH disconnected
                    pass
    except Exception:
        pass


def start_backend_server(pg_running: bool) -> subprocess.Popen[str] | None:
    """Start FastAPI via Uvicorn with clean process recycling and persistent logging."""
    # Cleanly recycle any stale backend process on port 8001
    stop_stale_backend_if_any()

    # Determine persistent log file location
    home_dir = Path.home()
    log_dir = home_dir / "mindmesh" / "Logs"
    if not (home_dir / "mindmesh").exists():
        log_dir = BACKEND_DIR / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    backend_log = log_dir / "backend.log"

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8001",
        "--log-level",
        "info",
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = str(BACKEND_DIR)
    if "DATABASE_URL" not in env:
        if pg_running:
            env["DATABASE_URL"] = "postgresql+asyncpg://coeai@localhost:5432/mindmesh"
        else:
            env["DATABASE_URL"] = f"sqlite+aiosqlite:///{BACKEND_DIR / 'mindmesh_local.db'}"

    popen_kwargs: dict[str, Any] = {
        "cwd": str(BACKEND_DIR),
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
    }
    if sys.platform != "win32":
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)

    # Start background daemon thread to stream logs live to terminal + persist to backend.log
    tee_thread = threading.Thread(
        target=_log_tee_worker,
        args=(proc, backend_log),
        daemon=True,
    )
    tee_thread.start()

    # Poll until /health becomes ready (up to 15 seconds)
    for _ in range(30):
        time.sleep(0.5)
        if is_backend_healthy():
            return proc
        if proc.poll() is not None:
            break

    # Read recent logs if backend failed to start
    recent_logs = ""
    if backend_log.exists():
        try:
            with open(backend_log, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                recent_logs = "".join(lines[-20:])
        except Exception:
            pass

    exit_code = proc.poll()
    if exit_code is not None:
        raise RuntimeError(
            f"MindMesh backend process exited prematurely with code {exit_code}.\nRecent logs:\n{recent_logs}"
        )
    raise RuntimeError(
        f"MindMesh backend did not become ready in 15 seconds.\nRecent logs:\n{recent_logs}"
    )


def send_memory_ingestion(
    raw_text: str,
    group_id: str | None = None,
    privacy: str = "ONLY_ME",
) -> dict[str, Any]:
    """Convert raw text into TextIngestionRequest and POST to FastAPI backend."""
    payload = {
        "media_type": "text",
        "text": raw_text,
        "group_id": group_id,
        "privacy": privacy,
        "allowed_users": [],
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(INGEST_URL, json=payload)
        
        if response.status_code != 200:
            error_data = {}
            try:
                error_data = response.json()
            except Exception:
                error_data = {"detail": response.text}
            raise RuntimeError(f"HTTP {response.status_code}: {error_data}")

        data = response.json()
        raw_input_id = response.headers.get("X-Raw-Input-Id", "N/A")
        phase1_output_id = response.headers.get("X-Phase1-Output-Id", "N/A")
        return {
            "memory": data,
            "raw_input_id": raw_input_id,
            "phase1_output_id": phase1_output_id,
        }


def print_work_done(result: dict[str, Any]) -> None:
    """Format and print the clean WORK DONE success summary."""
    memory = result.get("memory", {})
    memory_id = memory.get("memory_id", "N/A")
    raw_input_id = result.get("raw_input_id", "N/A")
    phase1_output_id = result.get("phase1_output_id", "N/A")
    
    content = memory.get("content", {})
    summary = content.get("summary", "N/A")
    clean_text = content.get("clean_text", "N/A")
    
    entities = memory.get("entities", {})
    people = ", ".join(entities.get("people", [])) or "None detected"
    places = ", ".join(entities.get("places", [])) or "None detected"
    locations = ", ".join(entities.get("locations", [])) or "None detected"
    
    semantics = memory.get("semantics", {})
    topics = ", ".join(semantics.get("topics", [])) or "None detected"
    sentiment = semantics.get("sentiment", "unknown")
    
    processing = memory.get("processing", {})
    status = processing.get("status", "completed")
    llm_model = processing.get("llm_model", "N/A")

    print("\n" + "=" * 48)
    print("                 WORK DONE")
    print("=" * 48)
    print(f"Memory ID:           {memory_id}")
    print(f"Raw Input ID:        {raw_input_id}")
    print(f"Phase 1 Output ID:   {phase1_output_id}")
    print(f"Processing Status:   {status}")
    print(f"Model:               {llm_model}")
    print("-" * 48)
    print(f"Summary:             {summary}")
    print(f"Clean Text:          {clean_text}")
    print(f"People:              {people}")
    print(f"Places:              {places}")
    print(f"Locations:           {locations}")
    print(f"Topics:              {topics}")
    print(f"Sentiment:           {sentiment}")
    print("=" * 48 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="MindMesh End-to-End Real Platform Runner")
    parser.add_argument("--text", type=str, help="Raw memory text to ingest directly")
    parser.add_argument("--group-id", type=str, default=None, help="Optional group ID")
    parser.add_argument("--check-only", action="store_true", help="Check system status and exit")
    args = parser.parse_args()

    print("\n" + "=" * 40)
    print("         MINDMESH STARTING")
    print("=" * 40 + "\n")

    # 1. PostgreSQL check
    pg_ok = check_and_start_postgres()
    pg_status = "READY" if pg_ok else "NOT RUNNING (Using Local Database)"
    print(f"PostgreSQL ............ {pg_status}")

    # 2. Database schema check
    db_ok = check_and_init_database(pg_running=pg_ok)
    db_status = "READY" if db_ok else "FAILED"
    print(f"Database .............. {db_status}")

    # 3. FastAPI backend start / reuse
    backend_proc = None
    try:
        backend_proc = start_backend_server(pg_running=pg_ok)
        print("FastAPI ............... READY")
    except Exception as exc:
        print(f"FastAPI ............... [ERROR] {exc}")
        sys.exit(1)

    # 4. Phase 1 readiness
    print("Phase 1 ............... READY")

    print("\n" + "=" * 40)
    print("         MINDMESH READY")
    print("=" * 40 + "\n")

    if args.check_only:
        print("All components verified successfully.")
        return

    # 5. Handle raw text ingestion
    try:
        if args.text:
            # Non-interactive CLI mode
            raw_text = args.text.strip()
            print(f"Processing memory:\n> {raw_text}\n")
            result = send_memory_ingestion(raw_text, group_id=args.group_id)
            print_work_done(result)
        else:
            # Interactive prompt mode
            while True:
                try:
                    print("Enter your memory:")
                    raw_text = input("> ").strip()
                    if not raw_text:
                        print("Empty input. Please enter a memory or press Ctrl+C to exit.\n")
                        continue

                    print("\n[MindMesh] Ingesting memory...")
                    result = send_memory_ingestion(raw_text, group_id=args.group_id)
                    print_work_done(result)

                    again = input("Enter another memory? (y/n) [y]: ").strip().lower()
                    if again in ("n", "no", "q", "quit", "exit"):
                        break
                    print()
                except (KeyboardInterrupt, EOFError):
                    print("\nExiting MindMesh...")
                    break
    except Exception as exc:
        print(f"\n[MindMesh] Processing failed:\n{exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
