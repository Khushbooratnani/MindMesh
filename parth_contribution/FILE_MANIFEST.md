# MindMesh — File Manifest
## Individual Contribution: Parth — Private Locker & Groups

> All files copied from `MindMesh-main` workspace. No files were modified during copying.
> Original source paths are relative to: `D:\final mindmesh work\final mindmesh work\`

---

## Component 1 — Private Locker

### Backend Files

| Component | Original File Path | Copied File Path | Purpose | Ownership Evidence | Dependency Status |
|-----------|-------------------|-----------------|---------|-------------------|------------------|
| Private Locker | `MindMesh-main/backend/app/api/routes/locker.py` | `Private_Locker/Backend/app/api/routes/locker.py` | FastAPI route handlers: create, unlock, lock, status, change-password, recover | Primary owner — locker-specific router | **PRIMARY CONTRIBUTION** |
| Private Locker | `MindMesh-main/backend/app/services/locker_service.py` | `Private_Locker/Backend/app/services/locker_service.py` | Core locker business logic: session management, idle timeout, brute-force lockout, password recovery | Primary owner — locker-specific service class | **PRIMARY CONTRIBUTION** |
| Private Locker | `MindMesh-main/backend/app/database/models/locker.py` | `Private_Locker/Backend/app/database/models/locker.py` | PrivateLockerModel + LockerSessionModel database tables | Primary owner — locker-specific models | **PRIMARY CONTRIBUTION** |
| Private Locker | `MindMesh-main/backend/app/database/migrations/003_auth_and_locker.sql` | `Private_Locker/Backend/app/database/migrations/003_auth_and_locker.sql` | SQL schema: private_lockers, locker_sessions, users, user_sessions | Primary owner — locker migration authored | **PRIMARY CONTRIBUTION** |
| Private Locker | `MindMesh-main/backend/app/api/dependencies/auth.py` | `Private_Locker/Backend/app/api/dependencies/auth.py` | get_current_user + get_active_locker_session FastAPI dependencies | Co-authored for locker session validation | **PRIMARY CONTRIBUTION** |
| Shared Dep | `MindMesh-main/backend/app/api/routes/auth.py` | `Private_Locker/Backend/app/api/routes/auth.py` | User registration, login, logout endpoints | Shared team code — required for user identity | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/services/auth_service.py` | `Private_Locker/Backend/app/services/auth_service.py` | AuthService: register, login, session management, Argon2id/SHA-256 hashing | Shared team code — required for authentication | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/database/models/user.py` | `Private_Locker/Backend/app/database/models/user.py` | UserModel + UserSessionModel | Shared team code — user identity tables | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/database/models/base.py` | `Private_Locker/Backend/app/database/models/base.py` | SQLAlchemy Base, GUID type, TimestampMixin | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/database/connection/session.py` | `Private_Locker/Backend/app/database/connection/session.py` | Async DB engine + session factory | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/config.py` | `Private_Locker/Backend/app/config.py` | App settings (includes private_locker_idle_timeout_seconds) | Shared config — locker timeout setting is locker-specific | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/core/errors.py` | `Private_Locker/Backend/app/core/errors.py` | Custom exception hierarchy | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/core/logging.py` | `Private_Locker/Backend/app/core/logging.py` | Logging configuration | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/core/enums.py` | `Private_Locker/Backend/app/core/enums.py` | Privacy enum (PRIVATE_LOCKER value) | Shared team code | **SHARED DEPENDENCY** |

### Frontend Files

| Component | Original File Path | Copied File Path | Purpose | Ownership Evidence | Dependency Status |
|-----------|-------------------|-----------------|---------|-------------------|------------------|
| Private Locker | `mindmesh-mobile/src/screens/LockerScreen.tsx` | `Private_Locker/Frontend/src/screens/LockerScreen.tsx` | Complete Locker UI: create/unlock/lock states, password input, error display | Primary owner — locker-specific screen | **PRIMARY CONTRIBUTION** |
| Private Locker | `mindmesh-mobile/src/auth/AuthContext.tsx` | `Private_Locker/Frontend/src/auth/AuthContext.tsx` | Auth + Locker React context: createLocker, unlockLocker, lockLocker, 120s timer | Primary owner — locker state management | **PRIMARY CONTRIBUTION** |
| Private Locker | `mindmesh-mobile/src/auth/authService.ts` | `Private_Locker/Frontend/src/auth/authService.ts` | API client: locker API calls + X-Locker-Token header injection | Primary owner — locker API integration | **PRIMARY CONTRIBUTION** |
| Private Locker | `mindmesh-mobile/src/auth/authStorage.ts` | `Private_Locker/Frontend/src/auth/authStorage.ts` | In-memory session + locker token storage | Primary owner — locker token storage | **PRIMARY CONTRIBUTION** |
| Private Locker | `mindmesh-mobile/src/auth/authTypes.ts` | `Private_Locker/Frontend/src/auth/authTypes.ts` | TypeScript types for auth + locker state | Primary owner — locker type definitions | **PRIMARY CONTRIBUTION** |
| Shared Dep | `mindmesh-mobile/src/screens/LoginScreen.tsx` | `Private_Locker/Frontend/src/screens/LoginScreen.tsx` | Login screen (required for locker access flow) | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `mindmesh-mobile/src/screens/SignUpScreen.tsx` | `Private_Locker/Frontend/src/screens/SignUpScreen.tsx` | Registration screen (required for user creation) | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `mindmesh-mobile/src/config/apiConfig.ts` | `Private_Locker/Frontend/src/config/apiConfig.ts` | API base URL configuration | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `mindmesh-mobile/src/types/index.ts` | `Private_Locker/Frontend/src/types/index.ts` | App-wide TypeScript types | Shared team code | **SHARED DEPENDENCY** |

### Test Files

| Component | Original File Path | Copied File Path | Purpose | Ownership Evidence | Dependency Status |
|-----------|-------------------|-----------------|---------|-------------------|------------------|
| Private Locker | `MindMesh-main/backend/test_locker.py` | `Private_Locker/Tests/test_locker.py` | Locker unit tests | Primary owner — locker-specific tests | **PRIMARY CONTRIBUTION** |
| Private Locker | `MindMesh-main/backend/e2e_locker_test.py` | `Private_Locker/Tests/e2e_locker_test.py` | End-to-end locker integration tests | Primary owner — locker-specific e2e | **PRIMARY CONTRIBUTION** |
| Shared Dep | `MindMesh-main/backend/tests/conftest.py` | `Private_Locker/Tests/conftest.py` | Pytest fixtures: in-memory SQLite, auth dependency overrides | Shared test infrastructure | **SHARED DEPENDENCY** |

---

## Component 2 — Groups System

### Backend Files

| Component | Original File Path | Copied File Path | Purpose | Ownership Evidence | Dependency Status |
|-----------|-------------------|-----------------|---------|-------------------|------------------|
| Groups | `MindMesh-main/backend/app/api/routes/groups.py` | `Groups/Backend/app/api/routes/groups.py` | FastAPI routes: create group, list groups, add/remove members | Primary owner — groups-specific router | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/app/services/group_service.py` | `Groups/Backend/app/services/group_service.py` | GroupService: create_group, add_member, remove_member with role enforcement | Primary owner — groups business logic | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/app/services/share_service.py` | `Groups/Backend/app/services/share_service.py` | ShareService: share_memory, revoke_access, group/user ACL management | Primary owner — memory sharing logic | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/app/services/authz_service.py` | `Groups/Backend/app/services/authz_service.py` | AuthorizationService: can_read_memory, get_accessible_memory_ids_query | Primary owner — group-aware access control | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/app/database/models/groups.py` | `Groups/Backend/app/database/models/groups.py` | GroupModel, GroupMemberModel, MemoryGroupAccessModel, MemoryUserAccessModel, GroupFeedReferenceModel | Primary owner — groups-specific models | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/app/database/migrations/004_groups_and_sharing.sql` | `Groups/Backend/app/database/migrations/004_groups_and_sharing.sql` | SQL schema: groups, group_members, memory_group_access, memory_user_access, group_feed_references, comments | Primary owner — groups migration | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/app/schemas/group.py` | `Groups/Backend/app/schemas/group.py` | Pydantic schemas: GroupCreateRequest, GroupResponse, AddMemberRequest, GroupMemberResponse | Primary owner — groups-specific schemas | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/app/api/routes/comments.py` | `Groups/Backend/app/api/routes/comments.py` | Comment routes: create, list, delete | Primary owner — comments are part of groups system | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/app/services/comment_service.py` | `Groups/Backend/app/services/comment_service.py` | CommentService: add_comment with knowledge eligibility, delete_comment with derived memory sync | Primary owner — comments logic | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/app/database/models/comments.py` | `Groups/Backend/app/database/models/comments.py` | CommentModel with knowledge_eligible + derived_memory_id | Primary owner — groups comments model | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/app/schemas/comment.py` | `Groups/Backend/app/schemas/comment.py` | CommentCreateRequest, CommentResponse | Primary owner — comment schemas | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/app/services/memory_search_service.py` | `Groups/Backend/app/services/memory_search_service.py` | Phase 3 search with group-aware ACL filtering | Groups integration into search pipeline | **PRIMARY CONTRIBUTION** |
| Shared Dep | `MindMesh-main/backend/app/api/routes/auth.py` | `Groups/Backend/app/api/routes/auth.py` | User registration/login | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/services/auth_service.py` | `Groups/Backend/app/services/auth_service.py` | AuthService | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/database/models/user.py` | `Groups/Backend/app/database/models/user.py` | UserModel | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/database/models/base.py` | `Groups/Backend/app/database/models/base.py` | SQLAlchemy Base, GUID | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/database/connection/session.py` | `Groups/Backend/app/database/connection/session.py` | DB session factory | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/config.py` | `Groups/Backend/app/config.py` | App settings | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/core/errors.py` | `Groups/Backend/app/core/errors.py` | Custom exceptions | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/core/logging.py` | `Groups/Backend/app/core/logging.py` | Logging config | Shared team code | **SHARED DEPENDENCY** |
| Shared Dep | `MindMesh-main/backend/app/core/enums.py` | `Groups/Backend/app/core/enums.py` | Privacy enum | Shared team code | **SHARED DEPENDENCY** |

### Frontend Files

| Component | Original File Path | Copied File Path | Purpose | Ownership Evidence | Dependency Status |
|-----------|-------------------|-----------------|---------|-------------------|------------------|
| Groups | `mindmesh-mobile/src/screens/GroupsScreen.tsx` | `Groups/Frontend/src/screens/GroupsScreen.tsx` | Groups screen scaffold — renders empty list | Partial implementation | **SCAFFOLD / PARTIAL** |

### Test Files

| Component | Original File Path | Copied File Path | Purpose | Ownership Evidence | Dependency Status |
|-----------|-------------------|-----------------|---------|-------------------|------------------|
| Groups | `MindMesh-main/backend/tests/test_groups_e2e.py` | `Groups/Tests/test_groups_e2e.py` | Basic group e2e test | Primary owner — groups test | **PRIMARY CONTRIBUTION** |
| Groups | `MindMesh-main/backend/tests/test_groups_full_e2e.py` | `Groups/Tests/test_groups_full_e2e.py` | Full comprehensive groups e2e test | Primary owner — groups test | **PRIMARY CONTRIBUTION** |
| Shared Dep | `MindMesh-main/backend/tests/conftest.py` | `Groups/Tests/conftest.py` | Pytest fixtures | Shared test infrastructure | **SHARED DEPENDENCY** |

---

## Files Intentionally Excluded

| File | Reason |
|------|--------|
| `.env` | Contains credentials/secrets — NEVER uploaded |
| `mindmesh_local.db` | Local database — NEVER uploaded |
| `venv/` | Python virtual environment |
| `node_modules/` | Node dependencies |
| `__pycache__/` | Python bytecode |
| `media_uploads/` | Uploaded media files |
| `*.zip` | Source archives |
| `app/orchestration/orchestrator.py` | Main Phase 1-2-3 pipeline — not my contribution |
| `app/services/ingestion_service.py` | Phase 1 ingestion — not my contribution |
| `app/services/embedding_service.py` | Phase 2 embedding — not my contribution |
| `app/services/phase2_service.py` | Phase 2 pipeline — not my contribution |
| `app/services/llm_service.py` | LLM pipeline — not my contribution |
| `app/services/whisper_service.py` | Audio transcription — not my contribution |
| `app/services/image_processor.py` | Image processing — not my contribution |
| `app/services/audio_processor.py` | Audio processing — not my contribution |
| `app/services/text_processor.py` | Text processing — not my contribution |
| `app/database/repositories/` | Phase 2 repositories — not my contribution |
| `app/tools/` | Dataset tools — not my contribution |
| `app/prompts/` | LLM prompts — not my contribution |
| `app/schemas/extraction_output.py` | Phase 1 output schemas — not my contribution |
| `mindmesh-—-ai-second-brain/` (web frontend) | Web frontend — not my contribution |
| Other test files | Not related to my contributions |

---

## Missing External Dependencies (NOT copied)

| Dependency | Component | Notes |
|-----------|----------|-------|
| `phase1_outputs` table | Both | Created by Phase 1 pipeline team |
| `raw_inputs` table | Both | Created by Phase 1 pipeline team |
| `phase2_embeddings` table | Groups (search) | Created by Phase 2 team |
| `app/database/repositories/phase2_embedding_repo.py` | Groups (search) | Phase 2 repository — not my contribution |
| `app/services/embedding_service.py` | Groups (search) | BAAI/bge-m3 model dependency |
| `app/services/llm_service.py` | Groups (search) | External LLM API |
| `app/database/migrations/001_initial_schema.sql` | Both | Phase 1 base schema |
| `app/database/migrations/002_phase2_schema.sql` | Both | Phase 2 schema |
| FastAPI app entrypoint `main.py` | Both | Registers all routers |

---

## Secrets Inspection Results

All copied files have been inspected. No hardcoded secrets, API keys, or passwords were found in the copied files.

- `config.py` contains a placeholder `auth_secret_key` — this is a default dev value, not a real secret.
- `config.py` contains default DB URL and LLM API URL — these are configuration values, not credentials.
- No `.env` files were copied.
- No database files (`.db`, `.sqlite`) were copied.
