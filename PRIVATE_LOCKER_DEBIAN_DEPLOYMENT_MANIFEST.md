# MINDMESH — PRIVATE LOCKER DEBIAN DEPLOYMENT MANIFEST
**Deployment Date:** For Controlled Deployment Tomorrow (October 24, 2026)  
**Target Debian Server:** `10.9.11.238`  
**SSH User:** `coeai`  
**Working-Copy Path:** `/home/coeai/mindmesh_copy/mindmesh`  
**Nested Backend Root:** `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app`  
**Frontend Root:** `/home/coeai/mindmesh_copy/mindmesh/mindmesh-mobile`  
**Working-Copy Backend Port:** `8002`  
**Protected Original:** `/home/coeai/mindmesh` (STRICTLY PROHIBITED TO MODIFY)

---

## 1. DEPLOYMENT PACKAGES

### Package A — Stability & Ingestion Fixes (High Priority)
- **Archive Name:** `MindMesh_Private_Locker_Stability_Fixes.zip`
- **Archive Size:** 31,519 bytes
- **SHA-256:** `02a5efdddb72c2b3674724353cdff57eeaa0c0ba1888bd266aebeefe42574dda`
- **Scope:** Normal ingestion repair (image/audio multipart), FastAPI Request parameter injection, Package A Phase 2 ciphertext fix, media authorization, stable server-based locker.

### Package B — Experimental Local-First Architecture (Optional / Staged)
- **Archive Name:** `MindMesh_Private_Locker_Local_First_Experimental.zip`
- **Archive Size:** 25,125 bytes
- **SHA-256:** `095f9a0309d52339a1de8dfce651197943dd6c454e3719523ff02e98a0c10d95`
- **Scope:** Separate `mindmesh_locker_auth` database, SQL migrations, ephemeral AI endpoints, client-side encryption, local vector search, and consent modal.

---

## 2. EXACT WINDOWS-TO-DEBIAN FILE MAPPING

### PACKAGE A: STABILITY & INGESTION FIXES

| Windows Source Path | Debian Destination Path | SHA-256 Checksum | Merge / Action |
| :--- | :--- | :--- | :--- |
| `backend\app\api\routes\memories.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/api/routes/memories.py` | `5a38aeed280a...` | Replace |
| `backend\app\orchestration\orchestrator.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/orchestration/orchestrator.py` | `6ea76be105a8...` | Replace |
| `backend\app\api\routes\media.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/api/routes/media.py` | `ea6bf6ed07ff...` | Replace |
| `backend\app\services\crypto_service.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/services/crypto_service.py` | `a6362bcee2a8...` | Replace |
| `backend\app\services\locker_service.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/services/locker_service.py` | `e2afc1663127...` | Replace |
| `backend\app\api\dependencies\auth.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/api/dependencies/auth.py` | `f86f3469653f...` | Replace |
| `backend\tests\test_memory_api.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/tests/test_memory_api.py` | `ec34a304c7f7...` | Replace / Add |
| `backend\tests\test_audio_ingestion.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/tests/test_audio_ingestion.py` | `f38b3d12816e...` | Replace / Add |
| `backend\tests\test_locker.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/tests/test_locker.py` | `873d1b67d748...` | Replace / Add |
| `backend\tests\test_locker_22_security_audit.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/tests/test_locker_22_security_audit.py` | `05e7e92f20f7...` | Replace / Add |
| `mindmesh-mobile\src\services\apiClient.ts` | `/home/coeai/mindmesh_copy/mindmesh/mindmesh-mobile/src/services/apiClient.ts` | `d6787c7edfb9...` | Replace |
| `mindmesh-mobile\src\config\apiConfig.ts` | `/home/coeai/mindmesh_copy/mindmesh/mindmesh-mobile/src/config/apiConfig.ts` | `b03e365f0338...` | Replace |

---

### PACKAGE B: EXPERIMENTAL LOCAL-FIRST LOCKER

| Windows Source Path | Debian Destination Path | SHA-256 Checksum | Merge / Action |
| :--- | :--- | :--- | :--- |
| `backend\app\local_first\__init__.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/local_first/__init__.py` | `4282236033f1...` | New Module |
| `backend\app\local_first\database.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/local_first/database.py` | `7764b50055d3...` | New Module |
| `backend\app\local_first\models.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/local_first/models.py` | `f2f800b955a1...` | New Module |
| `backend\app\local_first\schemas.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/local_first/schemas.py` | `53b96a2cdb7f...` | New Module |
| `backend\app\local_first\repository.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/local_first/repository.py` | `bcdf8ba00e4c...` | New Module |
| `backend\app\local_first\service.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/local_first/service.py` | `07eb6ca8d1c4...` | New Module |
| `backend\app\local_first\temporary_processing.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/local_first/temporary_processing.py` | `88c434d8888d...` | New Module |
| `backend\app\local_first\routes.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/local_first/routes.py` | `120ee4ee0be3...` | New Module |
| `backend\app\local_first\migrations\001_locker_auth_init.sql` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/local_first/migrations/001_locker_auth_init.sql` | `7c1cd9f4f81b...` | SQL Migration |
| `backend\app\local_first\migrations\001_locker_auth_rollback.sql` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/local_first/migrations/001_locker_auth_rollback.sql` | `6214743e4738...` | SQL Rollback |
| `backend\tests\test_local_first_auth.py` | `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/tests/test_local_first_auth.py` | `6331d6420849...` | New Test Suite |
| `mindmesh-mobile\src\local_first\types.ts` | `/home/coeai/mindmesh_copy/mindmesh/mindmesh-mobile/src/local_first/types.ts` | `5779c76f4807...` | Mobile Module |
| `mindmesh-mobile\src\local_first\deviceKeyManager.ts` | `/home/coeai/mindmesh_copy/mindmesh/mindmesh-mobile/src/local_first/deviceKeyManager.ts` | `0507b89248ce...` | Mobile Module |
| `mindmesh-mobile\src\local_first\localEncryptedStorage.ts` | `/home/coeai/mindmesh_copy/mindmesh/mindmesh-mobile/src/local_first/localEncryptedStorage.ts` | `d7ed377bc17d...` | Mobile Module |
| `mindmesh-mobile\src\local_first\localFirstAdapter.ts` | `/home/coeai/mindmesh_copy/mindmesh/mindmesh-mobile/src/local_first/localFirstAdapter.ts` | `c18d7bbe3965...` | Mobile Module |
| `mindmesh-mobile\src\local_first\ConsentGate.tsx` | `/home/coeai/mindmesh_copy/mindmesh/mindmesh-mobile/src/local_first/ConsentGate.tsx` | `bcd7055d3f6e...` | Mobile Component |

---

## 3. CONTROLLED DEPLOYMENT SEQUENCE (TOMORROW)

### Phase 1: Pre-Flight Safety & Backup
1. Verify working-copy status: Ensure backend on port 8002 is active.
2. Create snapshot backup of Debian working copy:
   ```bash
   cp -r /home/coeai/mindmesh_copy/mindmesh /home/coeai/backup_mindmesh_copy_pre_locker_$(date +%Y%m%d_%H%M%S)
   ```

### Phase 2: Deploy Package A (Stability Fixes)
1. Transfer `MindMesh_Private_Locker_Stability_Fixes.zip` to Debian server `/home/coeai/`.
2. Extract and apply files to the respective working-copy locations.
3. Validate backend imports:
   ```bash
   python3 -c "import app.main; print('Backend loaded successfully')"
   ```
4. Restart working-copy backend service on port 8002.
5. Run automated pytest test suite:
   ```bash
   pytest tests/test_memory_api.py tests/test_locker.py tests/test_audio_ingestion.py
   ```

### Phase 3: Deploy Package B (Experimental Local-First)
1. Create separate PostgreSQL database if enabled:
   ```sql
   CREATE DATABASE mindmesh_locker_auth;
   ```
2. Run migration:
   ```bash
   psql -d mindmesh_locker_auth -f app/local_first/migrations/001_locker_auth_init.sql
   ```
3. Extract Package B files into `/home/coeai/mindmesh_copy/mindmesh/backend/phase1_text_to_json_ingestion/app/local_first/`.
4. Run Local-First test suite:
   ```bash
   pytest tests/test_local_first_auth.py
   ```

---

## 4. ROLLBACK PROCEDURE

In the event of an unexpected regression on Debian:
1. Stop port 8002 backend process.
2. Restore from pre-deployment snapshot:
   ```bash
   rm -rf /home/coeai/mindmesh_copy/mindmesh
   cp -r /home/coeai/backup_mindmesh_copy_pre_locker_* /home/coeai/mindmesh_copy/mindmesh
   ```
3. If `mindmesh_locker_auth` was created and needs rollback:
   ```bash
   psql -d mindmesh_locker_auth -f app/local_first/migrations/001_locker_auth_rollback.sql
   ```
4. Restart backend service on port 8002 and verify health:
   ```bash
   curl http://127.0.0.1:8002/health
   ```
