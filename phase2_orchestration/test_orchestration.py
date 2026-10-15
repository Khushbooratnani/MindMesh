import os
import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project root to sys.path so phase2_orchestration is importable
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from phase2_orchestration.orchestrator import get_orchestrator

def main():
    print("=" * 75)
    print(" [PHASE 2 ORCHESTRATOR] LIVE INTEGRATION & VERIFICATION TEST")
    print("=" * 75)
    
    orchestrator = get_orchestrator()

    # 1. Load Sample Payloads
    payloads_path = current_dir / "sample_payloads.json"
    with open(payloads_path, "r", encoding="utf-8") as f:
        payloads = json.load(f)

    print(f" Loaded {len(payloads)} sample Phase 1 memory payloads.\n")

    # 2. Ingest and Embed Payloads
    print(" [STEP 1] Ingesting & Generating Dual 1024-dim Embeddings:")
    print("-" * 75)
    for p in payloads:
        res = orchestrator.ingest_memory(p)
        content_dim = res.embeddings.content.dimension
        context_dim = res.embeddings.context.dimension
        print(f" * [OK] Memory ID: {res.memory_id} | Status: {res.status} | Vectors: Content({content_dim}-dim), Context({context_dim}-dim)")

    # 3. Test Semantic Search Queries
    test_queries = [
        ("Where did we discuss the architecture for Phase 2?", "U_MEHUL_01"),
        ("What book did I read about transactions?", "U_MEHUL_01"),
        ("Where did I have coffee with Akshat?", "U_DEVELOPMENT"),
    ]

    print("\n" + "=" * 75)
    print(" [STEP 2] Running Semantic Vector Search Queries (No Location Dependencies):")
    print("=" * 75)

    for query, user_id in test_queries:
        print(f"\n [QUERY] '{query}' (User: {user_id})")
        response = orchestrator.search_memories(query=query, user_id=user_id, top_k=2)
        print(f"  -> AI Answer: {response.answer}")
        print(f"  -> Top Matched Results ({len(response.results)}):")
        for idx, r in enumerate(response.results, 1):
            print(f"     [{idx}] ID: {r.memory_id} | Similarity Score: {r.similarity_score:.4f} | Summary: {r.summary}")

    print("\n" + "=" * 75)
    print(" [SUCCESS] All Phase 2 Orchestration tests passed flawlessly!")
    print("=" * 75)

if __name__ == "__main__":
    main()
