# MindMesh Frontend Debian Integration Report

**Date:** 2026-10-23  
**Status:** DEPLOYED & MERGED — CODE VERIFIED, BACKEND RUNNING  
**Target Host:** Debian (`coeai@10.9.11.238`)  
**Target Path:** `/home/coeai/mindmesh_copy/mindmesh`  
**API Port:** `8002` (Original port `8001` strictly untouched)  

---

## 1. Scope & Execution

All Windows development frontend fixes and backend security allowlist components were safely staged, reviewed, and deployed to the authorized Debian working-copy project (`/home/coeai/mindmesh_copy/mindmesh`).

### 1.1 Backups Created
- **Windows Pre-Fix Backup**:  
  `F:\MindMesh-mindmesh-core\MindMesh-mindmesh-core\backups\windows_frontend_pre_master_fix_20261023\src`
- **Debian Working-Copy Pre-Fix Backup**:  
  `/home/coeai/mindmesh_copy/backups/debian_pre_master_fix_20261023_063000/`  
  (Contains full snapshots of `frontend_src` and `backend_app` with timestamped `MANIFEST.txt`).

---

## 2. File Verification & SHA-256 Checksums

Exact SHA-256 checksums verify byte-level integrity between Windows development source and Debian deployed files:

### Frontend Components (`mindmesh-mobile/src/`)
| File | Windows SHA-256 | Debian SHA-256 | Match |
| :--- | :--- | :--- | :--- |
| `services/uploadAdapter.ts` | `5ca12500cce14ae00628d9053844f5328d0e22c12b68491d42e64618b814d7f8` | `5ca12500cce14ae00628d9053844f5328d0e22c12b68491d42e64618b814d7f8` | **YES** |
| `services/apiClient.ts` | `6a45d55b0c16fb070cc5b9dae3e02f274dcf26eef78b0cc52042dcc335133f5b` | `6a45d55b0c16fb070cc5b9dae3e02f274dcf26eef78b0cc52042dcc335133f5b` | **YES** |
| `screens/ComposerScreen.tsx` | `e2259fe4860311bfd16560582a68630c99f10254cae14b6563523801420de85d` | `e2259fe4860311bfd16560582a68630c99f10254cae14b6563523801420de85d` | **YES** |
| `screens/LockerScreen.tsx` | `161da2c72bf0013cffba371c98337dac31c2c9cf937d64673aa340504cec2f49` | `161da2c72bf0013cffba371c98337dac31c2c9cf937d64673aa340504cec2f49` | **YES** |
| `screens/VaultScreen.tsx` | `a67b8e21547906faabf3bd72cbbf5f1b9679e1218f10f0faaa9c9a7dd0446215` | `a67b8e21547906faabf3bd72cbbf5f1b9679e1218f10f0faaa9c9a7dd0446215` | **YES** |
| `screens/GroupsScreen.tsx` | `e1aff9769bd30f8255157388e45a0910e931e126309e9bce44c24441885b953f` | `e1aff9769bd30f8255157388e45a0910e931e126309e9bce44c24441885b953f` | **YES** |

### Backend Components (`backend/phase1_text_to_json_ingestion/`)
| File | Debian SHA-256 | Description |
| :--- | :--- | :--- |
| `app/config.py` | `d68f2aec5f7a2a83137f2ef84dcaf65f25b94ac86bff33c11de806827e64cf26` | Preserved `mindmesh_copy` db; added `local_first_test_user_allowlist = []`. |
| `app/main.py` | `7d81c1337dc838d71549dc6968c6101efe2cbeb56f14b833dc9798abae727347` | Enforces `verify_local_first_access` on all `/api/v2/*` routes. |
| `tests/test_local_first_auth.py` | `9c6042358681ed90ef799bca13d0d723d1990bddd96fa1030b479e693c5c7209` | Validates allowlist default-deny & complete 8-stage authentication flow. |

---

## 3. Merge Decisions & Configuration Preservation

1. **Database Configuration**:
   - Preserved `database_url: str = "postgresql+asyncpg://coeai@localhost:5432/mindmesh_copy"` on Debian working copy.
   - Preserved `locker_auth_database_url: str = "postgresql+asyncpg://coeai@localhost:5432/mindmesh_locker_auth"`.
   - Never modified or touched original database `mindmesh` on port 8001.
2. **API Endpoint & Metro Bundle Routing**:
   - Expo runtime configuration strictly preserves `EXPO_PUBLIC_API_URL=http://10.9.11.238:8002`.
   - The active Metro server runs on Windows (`f:\MindMesh-mindmesh-core\MindMesh-mindmesh-core\mindmesh-mobile`), serving the updated bundle directly to Expo Go over local Wi-Fi.
   - Synchronizing both Windows and Debian frontends ensures that either host can serve identical JavaScript bundles without discrepancy.

---

## 4. Test Results

- **TypeScript Compilation (Debian)**: `npx tsc --noEmit` -> **0 errors, Exit code 0**
- **Package A Core Regression (Debian)**: `pytest tests/test_locker.py tests/test_text_ingestion.py tests/test_schema_validation.py` -> **5 passed in 0.77s**
- **Package B Local-First Auth Flow (Debian)**: `pytest tests/test_local_first_auth.py` -> **1 passed in 1.97s**
- **Live Port 8002 Health Check**: `curl -s http://127.0.0.1:8002/health` -> `{"status":"ok"}`

---

## 5. Deployment Gate & Next Actions

- **Backend Port 8002 Daemon**:
  - The live backend process on port 8002 (PID `45834`) continues to run healthily.
  - In accordance with non-negotiable safety rules ("Request explicit approval before service restarts"), the process has **NOT** been restarted.
  - When the user approves a graceful restart, the updated `main.py` route dependency and `config.py` allowlist will be loaded into process memory.
