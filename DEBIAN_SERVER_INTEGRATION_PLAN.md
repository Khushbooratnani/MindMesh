# MindMesh — Complete Private Locker Integration & Deferred Server Deployment Plan

## Executive Summary
This document serves as the comprehensive server integration manifest, database compatibility guide, and deployment handbook for transitioning the verified Windows implementation of the **Private Locker** module to the Debian server environment.

In accordance with strict safety mandates, **no connections, migrations, or file alterations were made to the remote Debian server during this phase**. All backend authentication, Argon2id security controls, AES-256-GCM authenticated encryption, ACL filtering, Phase 1-2-3 pipeline interfaces, frontend screens, and automated regression suites have been integrated and locally verified on Windows.

---

## 1. Deployment Target Architecture

| Component | Path / Detail | Status |
|---|---|---|
| **Future Deployment Target** | `/home/coeai/mindmesh_copy` | Pending User Approval |
| **Protected Original Baseline** | `/home/coeai/mindmesh` | **PRESERVED & UNTOUCHED** |
| **Local Source Workspace** | `F:\MindMesh-mindmesh-core\MindMesh-mindmesh-core` | Complete & Locally Verified |
| **Pre-Integration Backup** | `F:\MindMesh-mindmesh-core_backup_pre_locker_20261021` | Verified & Restorable |

---

## 2. File-by-File Deployment Manifest

The following files represent the exact set of modified and added components to sync to `/home/coeai/mindmesh_copy`:

### Backend Components Added / Modified:
1. `backend/app/database/migrations/003_auth_and_locker.sql` *(Added)* — Creates `users`, `user_sessions`, `private_lockers`, `locker_sessions`, and adds `owner_id`, `privacy` columns.
2. `backend/app/database/migrations/003_rollback_auth_and_locker.sql` *(Added)* — Safe rollback script for schema reversal.
3. `backend/app/database/migrations/runner.py` *(Added)* — Python migration runner supporting idempotent schema execution.
4. `backend/app/database/models/user.py` *(Added)* — SQLAlchemy models `UserModel` and `UserSessionModel`.
5. `backend/app/database/models/locker.py` *(Added)* — SQLAlchemy models `PrivateLockerModel` and `LockerSessionModel`.
6. `backend/app/database/models/raw_input.py` *(Updated)* — Added `owner_id` (ForeignKey to `users.id`) and `privacy`.
7. `backend/app/database/models/phase1_output.py` *(Updated)* — Added `owner_id` (ForeignKey to `users.id`) and `privacy`.
8. `backend/app/database/models/__init__.py` *(Updated)* — Central export of all database models.
9. `backend/app/database/repositories/raw_input_repo.py` *(Updated)* — Locker filtering, private feed queries, owner and privacy mapping.
10. `backend/app/database/repositories/phase1_output_repo.py` *(Updated)* — Added `owner_id` and `privacy` extraction and persistence.
11. `backend/app/database/repositories/phase2_embedding_repo.py` *(Updated)* — pgvector cosine distance search with central ACL filtering and SQLite test fallback.
12. `backend/app/core/enums.py` *(Updated)* — Added `Privacy.PRIVATE_LOCKER = "PRIVATE_LOCKER"`.
13. `backend/app/config.py` *(Updated)* — Added locker security parameters (`jwt_secret_key`, `locker_encryption_key`, timeout thresholds).
14. `backend/app/services/crypto_service.py` *(Added)* — AES-256-GCM authenticated encryption service with `enc:v1:` prefix and legacy text fallback.
15. `backend/app/services/auth_service.py` *(Added)* — Argon2id password hashing and session management.
16. `backend/app/services/locker_service.py` *(Added)* — Locker creation, unlocking, 5-attempt lockout enforcement, recovery key rotation.
17. `backend/app/services/authz_service.py` *(Added)* — Multi-tenant ACL authorization query builder with groups compatibility.
18. `backend/app/services/memory_search_service.py` *(Updated)* — Decrypts private memories only when `locker_session_valid` is true; eliminates hardcoded IP addresses.
19. `backend/app/orchestration/orchestrator.py` *(Updated)* — Encrypts sensitive raw payloads before DB storage, decrypts in-memory for extraction, encrypts Phase 1 output content, forwards `owner_id` and `privacy`.
20. `backend/app/api/dependencies/auth.py` *(Added)* — `get_current_user` and `get_active_locker_session` dependency injectors.
21. `backend/app/api/routes/auth.py` *(Added)* — `/register`, `/login`, `/logout`, `/me` endpoints.
22. `backend/app/api/routes/locker.py` *(Added)* — `/create`, `/unlock`, `/lock`, `/status`, `/memories`, `/change-password`, `/recover` endpoints.
23. `backend/app/api/routes/media.py` *(Updated)* — Enforces active locker session verification before streaming `PRIVATE_LOCKER` media files.
24. `backend/app/api/routes/memories.py` *(Updated)* — Locker validation for ingestion, groups isolation, inventory leakage protection, unlocked feed stream, and ACL semantic search.
25. `backend/app/main.py` *(Updated)* — Registered `auth_router` and `locker_router`; exposed `X-Locker-Token` header.
26. `backend/tests/conftest.py` *(Updated)* — Added default `U_DEVELOPMENT` user setup in in-memory test DB.
27. `backend/tests/test_locker_22_security_audit.py` *(Added)* — Full 22-point automated security audit suite.
28. `backend/tests/test_locker.py` *(Added)* — End-to-end vector search, ACL, feed isolation, and LLM context isolation suite.

### Frontend Components (`mindmesh-mobile`):
1. `src/types/index.ts` — Added `'locker'` to `ScreenId` and `'PRIVATE_LOCKER'` to `Privacy`.
2. `src/auth/authTypes.ts` — Added locker state interfaces (`lockerExists`, `isLockerUnlocked`, `lockerExpiresAt`, `isLockerLoading`) and action signatures.
3. `src/auth/authStorage.ts` — Added `getLockerToken()`, `setLockerToken()`, `clearLockerToken()`.
4. `src/auth/authService.ts` — Wired real backend API calls for auth and locker operations.
5. `src/auth/AuthContext.tsx` — Real backend authentication context with automatic 120-second inactivity lock timer.
6. `src/services/apiClient.ts` — Added `Authorization` and `X-Locker-Token` headers to all requests; added locker API wrappers.
7. `src/services/memoryAdapter.ts` — Dynamic IP relative media URL resolution via `getApiUrl`.
8. `src/screens/LockerScreen.tsx` — Complete Private Locker UI (initialize, unlock, auto-lock, recovery, change password, memory stream).
9. `src/components/FloatingBottomDock.tsx` — Added dedicated Private Locker bottom dock tab.
10. `src/screens/ComposerScreen.tsx` — Added Private Locker (Secured) destination option in memory composer.
11. `App.tsx` — Registered `LockerScreen` routing.

---

## 3. Server Database Compatibility Checklist

When inspecting the actual Debian PostgreSQL database on `/home/coeai/mindmesh_copy`, perform these checks in order:

### 1. User & Account Table Verification
- Query: `SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users';`
- If `users` already exists with a different primary key type (e.g. `INTEGER` vs `VARCHAR(64)`):
  - Adapt `UserModel.id` in `user.py` to match the existing column type.
  - Verify that `U_DEVELOPMENT` or existing user UUIDs align.

### 2. Existing Memory Tables (`raw_inputs`, `phase1_outputs`)
- Query: `SELECT column_name FROM information_schema.columns WHERE table_name = 'raw_inputs' AND column_name IN ('owner_id', 'privacy');`
- If `owner_id` or `privacy` already exist:
  - Check their column definitions and nullability constraints.
  - The migration script uses `ADD COLUMN IF NOT EXISTS`, preventing errors if columns are already present.

### 3. pgvector & Embedding Dimensions
- Query: `SELECT proname FROM pg_proc WHERE proname = 'cosine_distance';`
- Query: `SELECT atttypmod FROM pg_attribute WHERE attrelid = 'phase2_embeddings'::regclass AND attname = 'content_vector';`
- If the server uses 1024 dimensions (BAAI/bge-m3 default in MindMesh Phase 2), no change is needed.
- If the server uses 768 or 1536 dimensions, update `vector(1024)` in `002`/`003` migrations to match.

### 4. Existing Unencrypted Data Migration (Optional)
- Historical memories stored prior to this integration remain accessible because `locker_crypto.decrypt` includes an automatic backward-compatibility fallback (returns plaintext as-is if the `enc:v1:` prefix is absent).
- No destructive or irreversible data rewrites are required for existing memories.

---

## 4. Server Migration Execution Instructions

### Step 1: Sync Code to `mindmesh_copy`
```bash
# Verify destination directory
ls -la /home/coeai/mindmesh_copy

# Copy integrated backend and frontend files from Windows workspace to /home/coeai/mindmesh_copy
```

### Step 2: Install Python Dependencies
```bash
cd /home/coeai/mindmesh_copy/backend
source /home/coeai/mindmesh_copy/venv/bin/activate  # or server virtualenv
pip install "cryptography>=42.0.0" "argon2-cffi>=23.1.0"
```

### Step 3: Configure Environment Variables
Create or update `/home/coeai/mindmesh_copy/backend/.env`:
```ini
# Production JWT Secret Key (required in production, minimum 32 characters)
JWT_SECRET_KEY=generate_with_openssl_rand_hex_32

# Locker AES-256-GCM Encryption Key (optional, defaults to deriving from JWT_SECRET_KEY)
LOCKER_ENCRYPTION_KEY=generate_with_openssl_rand_base64_32

# Application Environment
APP_ENV=production
```

### Step 4: Execute Database Migration
```bash
# Run SQL migration using psql:
psql -U mindmesh_user -d mindmesh_db -f backend/app/database/migrations/003_auth_and_locker.sql

# OR via the Python runner:
python -m app.database.migrations.runner
```

### Step 5: Verify Server Database Tables
```sql
\dt private_lockers
\dt locker_sessions
\dt user_sessions
\d+ phase1_outputs
```

### Step 6: Execute Server-Side Automated Verification
```bash
cd /home/coeai/mindmesh_copy/backend
pytest tests/test_locker_22_security_audit.py -v -s
pytest tests/test_locker.py -v -s
pytest tests/ -v
```

---

## 5. Migration Rollback Plan

If schema reversion is required on the server:
```bash
psql -U mindmesh_user -d mindmesh_db -f backend/app/database/migrations/003_rollback_auth_and_locker.sql
```
This cleanly drops `private_lockers`, `locker_sessions`, and `user_sessions`, and removes `privacy` and `owner_id` columns without affecting original user records or baseline memory content.
