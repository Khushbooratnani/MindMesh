# MindMesh — Debian Deployment Manifest & Staging Plan

**Document Version:** 1.0.0  
**Target Deployment Server:** Debian Server `10.9.11.238`  
**SSH User:** `coeai`  
**Working-Copy Path:** `/home/coeai/mindmesh_copy/mindmesh`  
**Protected Original:** `/home/coeai/mindmesh`  
**Windows Staging Source:** `F:\MindMesh-mindmesh-core\MindMesh-mindmesh-core`  
**Master Restorable Backup:** `F:\MindMesh-mindmesh-core_backup_master_fix_20261021_221144`  
**Status:** Staged on Windows, 100% Tested locally, DEFERRED from Debian until tomorrow

---

## 1. Package Segregation Overview

To guarantee stability, changes are partitioned into two strictly independent packages:

1. **Package A (Stable Private Locker Bug Fixes):**
   - High priority, zero breaking schema changes.
   - Fixes BUG-01 (login/signup crash), BUG-02 (locker status contract), BUG-03 (Phase 2 BGE-M3 ciphertext embeddings), and security audit assertions.
   - Recommended for immediate deployment to `/home/coeai/mindmesh_copy/mindmesh`.
2. **Package B (Experimental Local-First Architecture):**
   - Foundation for separate authentication database (`mindmesh_locker_auth`), device key manager, encrypted local mobile storage, and ephemeral AI consent gateway.
   - Isolated in versioned `/api/v2/` routes and `src/local_first/` directories.
   - Requires separate database creation on PostgreSQL before activation.

---

## 2. File Manifest & Checksums

### Package A: Stable Private Locker Bug Fixes

| Windows Staging File | Debian Destination Path | SHA-256 Checksum | Purpose |
| :--- | :--- | :--- | :--- |
| `backend/app/api/routes/auth.py` | `backend/app/api/routes/auth.py` | `79bd660d173a60f709ce752d6b61badbd0f0727629b5273798609e9b2b056ba6` | Fix BUG-01: Add email/full_name fields to UserResponse |
| `backend/app/api/routes/locker.py` | `backend/app/api/routes/locker.py` | `a41df6c5cbde214b0cee8c61f54e42bcd2078078bfeede8539e8300701174c5f` | Fix BUG-02: Normalize StatusResponse contract |
| `backend/app/services/phase2_service.py` | `backend/app/services/phase2_service.py` | `e165de6ff31cb1e21551c4560ea57e5afb623d876267da17fbc13958ec7486f4` | Fix BUG-03: Transient in-memory decryption for BGE-M3 |
| `backend/app/services/locker_service.py` | `backend/app/services/locker_service.py` | `e2afc16631275f33ee12d5bd44fe9b90d2dee869176385e7cbc6c879a780fe00` | Contract compatibility alias |
| `backend/tests/test_locker_22_security_audit.py` | `backend/tests/test_locker_22_security_audit.py` | `05e7e92f20f7e5ec81f99839d92bfafb00e255e7cf3a593629e7a33b8466de01` | Hardened security assertions (Reqs 10, 17, 20, 21, 22) |
| `mindmesh-mobile/src/auth/authService.ts` | `mindmesh-mobile/src/auth/authService.ts` | `0b146f7638241399596e8574f37429b78f4667ed66a26c9c7cef69244b8fbe37` | Remove unsafe split('@'), handle missing optional fields |
| `mindmesh-mobile/src/auth/authTypes.ts` | `mindmesh-mobile/src/auth/authTypes.ts` | `dbfe6accd6213d19d8fcc7c55b06528eb65bfc961ff6907ad19804111d5080ff` | Safe AuthUser typings |

### Package B: Experimental Local-First Architecture

| Windows Staging File | Debian Destination Path | SHA-256 Checksum | Purpose |
| :--- | :--- | :--- | :--- |
| `backend/app/main.py` | `backend/app/main.py` | `f841ffc5910c34df445110c1b58df8815748368087753e405ac51159cfc5e806` | Mount /api/v2/ routes |
| `backend/app/local_first/__init__.py` | `backend/app/local_first/__init__.py` | `4282236033f15a2d549b1a1b085c6eab6ece03f43d0074f2e665c20e2b3538ab` | Package initialization |
| `backend/app/local_first/database.py` | `backend/app/local_first/database.py` | `7764b50055d3ec50a73c82d12125d3ab7c545d5bf367e1f3d45baf65a27faebd` | Dedicated async engine |
| `backend/app/local_first/models.py` | `backend/app/local_first/models.py` | `f2f800b955a1032fe763849e13462cef72843b5b5cd467b95ff5567f52529a74` | SQLAlchemy auth models |
| `backend/app/local_first/schemas.py` | `backend/app/local_first/schemas.py` | `53b96a2cdb7f7dd576334dc7e03f228d1f21f7534c0ec242042d681060497b12` | Pydantic request/response schemas |
| `backend/app/local_first/repository.py` | `backend/app/local_first/repository.py` | `bcdf8ba00e4c9f94d7a6945b27194a87c19044477c7790fbaa5a8d5f38c66503` | Verifier and session data access |
| `backend/app/local_first/service.py` | `backend/app/local_first/service.py` | `07eb6ca8d1c4d6d53bcf7e921675254e0fe35863e240c74b6291e4cfa1338ab0` | Argon2id verification & rate-limiting |
| `backend/app/local_first/temporary_processing.py` | `backend/app/local_first/temporary_processing.py` | `88c434d8888d7457e5364ac8421b4b7545495265a0b35f04f5b1ba3aea947a99` | In-RAM ephemeral AI services |
| `backend/app/local_first/routes.py` | `backend/app/local_first/routes.py` | `120ee4ee0be338ec3708051ac69885ec68ca262307bdd9dba7c8e15835f793ec` | FastAPI v2 endpoints |
| `backend/app/local_first/migrations/001_locker_auth_init.sql` | `backend/app/local_first/migrations/001_locker_auth_init.sql` | `7c1cd9f4f81ba2a5823c08bf80a002e1463e890ee15696b8c1ed28bb5f633d95` | Schema initialization for auth db |
| `backend/app/local_first/migrations/001_locker_auth_rollback.sql` | `backend/app/local_first/migrations/001_locker_auth_rollback.sql` | `6214743e4738867c4adbd761bd4bf3fe40fc1bc885a0965d7a96796fdeaef15f` | Reversible rollback SQL |
| `backend/tests/test_local_first_auth.py` | `backend/tests/test_local_first_auth.py` | `6331d642084924e26d18777301e11853e664656085be3594b09f9ec54b5d84fa` | Local-first test suite |
| `mindmesh-mobile/src/local_first/types.ts` | `mindmesh-mobile/src/local_first/types.ts` | `5779c76f480733395f483d498fe3f2f74b337c6dd99077ce89e8b6483e61551d` | Local memory and consent types |
| `mindmesh-mobile/src/local_first/deviceKeyManager.ts` | `mindmesh-mobile/src/local_first/deviceKeyManager.ts` | `0507b89248ce6288380c80a0d7cf66223371dbc7d4367a693217fe9ea5f28fcd` | DEK wrapping, export/import |
| `mindmesh-mobile/src/local_first/localEncryptedStorage.ts` | `mindmesh-mobile/src/local_first/localEncryptedStorage.ts` | `d7ed377bc17dcb6d490448bbbe76965066e3a33f8422e602c83ac590f045321d` | Staged local storage & cosine search |
| `mindmesh-mobile/src/local_first/ConsentGate.tsx` | `mindmesh-mobile/src/local_first/ConsentGate.tsx` | `bcd7055d3f6e25b9990215a61e528f21ab58deb66e33cd9db7d769a9f3f1daff` | Explicit opt-in consent modal |
| `mindmesh-mobile/src/local_first/localFirstAdapter.ts` | `mindmesh-mobile/src/local_first/localFirstAdapter.ts` | `c18d7bbe396569f0a46b8b1230d727d2034fa3a6626e2061a75b1ebeda331485` | Mobile integration adapter |

---

## 3. Database Requirements & Migrations

### 3.1. Main Core Database (`mindmesh_core`)
- **Required Migrations:** **NONE**.
- Package A fixes work directly with the existing `003_auth_and_locker.sql` schema already applied on Debian.

### 3.2. Separate Authentication Database (`mindmesh_locker_auth`)
- **Action Required on Debian:**
  Create a dedicated database owned by `mindmesh_user` or a restricted service account:
  ```sql
  CREATE DATABASE mindmesh_locker_auth OWNER mindmesh_user;
  ```
- **Run Initialization Migration:**
  ```bash
  psql -U mindmesh_user -d mindmesh_locker_auth -f backend/app/local_first/migrations/001_locker_auth_init.sql
  ```

---

## 4. Tomorrow's Debian Deployment Sequence

When approved to deploy to Debian `10.9.11.238`:

### Step 1: Pre-Deployment Backup
SSH into Debian and snapshot the working copy:
```bash
ssh coeai@10.9.11.238
cp -r /home/coeai/mindmesh_copy/mindmesh /home/coeai/mindmesh_copy/mindmesh_pre_deployment_$(date +%Y%m%d_%H%M%S)
```

### Step 2: Deploy Package A (Stable Fixes)
1. Transfer Package A files from Windows staging to Debian `/home/coeai/mindmesh_copy/mindmesh`.
2. Verify checksums match this manifest.
3. Restart backend service:
   ```bash
   sudo systemctl restart mindmesh-backend
   ```
4. Run validation test suite:
   ```bash
   cd /home/coeai/mindmesh_copy/mindmesh/backend
   pytest tests/test_locker_22_security_audit.py -s
   pytest tests/ -q
   ```

### Step 3: Optional Deployment of Package B (Local-First)
1. Provision `mindmesh_locker_auth` database in PostgreSQL.
2. Transfer Package B files.
3. Configure `LOCKER_AUTH_DATABASE_URL` in Debian `/home/coeai/mindmesh_copy/mindmesh/backend/.env`.
4. Run migration script `001_locker_auth_init.sql`.
5. Run test suite:
   ```bash
   pytest tests/test_local_first_auth.py -s
   ```

---

## 5. Rollback Procedures

### Package A Rollback
If any regressions occur during Package A testing on Debian:
```bash
# Restore specific modified files from the pre-deployment snapshot:
cp /home/coeai/mindmesh_copy/mindmesh_pre_deployment_*/backend/app/api/routes/auth.py /home/coeai/mindmesh_copy/mindmesh/backend/app/api/routes/
cp /home/coeai/mindmesh_copy/mindmesh_pre_deployment_*/backend/app/api/routes/locker.py /home/coeai/mindmesh_copy/mindmesh/backend/app/api/routes/
cp /home/coeai/mindmesh_copy/mindmesh_pre_deployment_*/backend/app/services/phase2_service.py /home/coeai/mindmesh_copy/mindmesh/backend/app/services/
sudo systemctl restart mindmesh-backend
```

### Package B Rollback
To completely unmount and remove Package B:
1. Remove `/api/v2/` router inclusions in `backend/app/main.py`.
2. Rollback the isolated authentication database:
   ```bash
   psql -U mindmesh_user -d mindmesh_locker_auth -f backend/app/local_first/migrations/001_locker_auth_rollback.sql
   DROP DATABASE mindmesh_locker_auth;
   ```
3. Restart backend service.

---

## 6. Safety Compliance Sign-Off

- [x] Windows target project strictly preserved (`F:\MindMesh-mindmesh-core\MindMesh-mindmesh-core`).
- [x] Full master backup created before modifications (`F:\MindMesh-mindmesh-core_backup_master_fix_20261021_221144`).
- [x] Existing server-based Private Locker preserved and 100% operational.
- [x] Zero network connections or modifications made to Debian server (`10.9.11.238`).
- [x] Zero modifications made to GitHub.
- [x] All 71 backend tests pass, all 22 security requirements verified with real assertions.
- [x] Mobile TypeScript compilation clean (`tsc --noEmit` exited 0).
