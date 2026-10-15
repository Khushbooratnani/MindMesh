# MindMesh — Individual Contribution: Private Locker & Groups

**Author:** Parth  
**Branch:** `parth-private-locker-groups`  
**Project:** MindMesh — AI Second Brain Platform  
**Stack:** Python / FastAPI (Backend) · React Native / Expo (Mobile Frontend)

---

## Overview

This repository contains my individual contribution to the MindMesh team project. I designed and implemented two complete, independent features:

1. **Private Locker** — A secure, password-protected encrypted memory space with token-based session management.
2. **Groups System** — A full group memory-sharing and access-control system with role-based permissions.

Both systems are integrated into the MindMesh backend (FastAPI + PostgreSQL) and mobile frontend (React Native + Expo).

> **Note:** These components depend on the shared MindMesh infrastructure (database connection, base models, auth service). They cannot run standalone without the complete MindMesh application. Dependencies are clearly documented below.

---

## Component 1 — Private Locker

### Purpose

The Private Locker provides a secure, password-gated memory space inside MindMesh. Memories marked `PRIVATE_LOCKER` are only accessible when the user has actively unlocked their locker with their personal password and holds a valid locker session token.

### Features Implemented

- **Locker Creation** — User sets a unique locker password. A one-time recovery key is generated and returned only once.
- **Locker Unlock / Lock** — Password verification with Argon2id hashing. Returns a short-lived session token (`X-Locker-Token`).
- **Idle Timeout** — Locker sessions expire automatically after 120 seconds of inactivity (server-enforced, also tracked client-side).
- **Brute-Force Protection** — 5 failed attempts trigger a 5-minute lockout.
- **Password Change** — Old password required to set a new one.
- **Account Recovery** — Recovery key (stored as Argon2id hash) allows password reset without old password.
- **Locker Status Check** — Returns whether a locker exists and whether the user is locked out.
- **Privacy Enforcement** — `PRIVATE_LOCKER` memories are blocked from sharing and only visible to the owner with a valid locker session.

### Backend Implementation

| File | Purpose |
|------|---------|
| `Backend/app/api/routes/locker.py` | FastAPI routes: `/api/v1/locker/{create, unlock, lock, status, change-password, recover}` |
| `Backend/app/api/routes/auth.py` | User registration, login, logout, `/me` — required by locker for user identity |
| `Backend/app/api/dependencies/auth.py` | `get_current_user` (Bearer token) and `get_active_locker_session` (X-Locker-Token) FastAPI dependencies |
| `Backend/app/services/locker_service.py` | Core locker business logic: create, unlock, lock, idle timeout, change password, recover |
| `Backend/app/services/auth_service.py` | User registration, login, session management (Argon2id hashing, SHA-256 token hashing) |
| `Backend/app/database/models/locker.py` | `PrivateLockerModel` (locker config + lockout state), `LockerSessionModel` (active sessions with idle tracking) |
| `Backend/app/database/models/user.py` | `UserModel`, `UserSessionModel` (shared dependency) |
| `Backend/app/database/models/base.py` | SQLAlchemy `Base`, `GUID` type, `TimestampMixin` |
| `Backend/app/database/connection/session.py` | AsyncEngine + session factory (shared dependency) |
| `Backend/app/database/migrations/003_auth_and_locker.sql` | SQL schema: `users`, `user_sessions`, `private_lockers`, `locker_sessions` |
| `Backend/app/config.py` | `Settings` with `private_locker_idle_timeout_seconds=120`, DB URL, auth config |
| `Backend/app/core/errors.py` | Custom exception hierarchy |
| `Backend/app/core/logging.py` | Logging configuration |
| `Backend/app/core/enums.py` | `Privacy.PRIVATE_LOCKER` enum |

### API Endpoints

| Method | Route | Auth Required | Description |
|--------|-------|--------------|-------------|
| `POST` | `/api/v1/auth/register` | No | Register a new user |
| `POST` | `/api/v1/auth/login` | No | Login, get Bearer session token |
| `POST` | `/api/v1/auth/logout` | Bearer | Revoke session |
| `GET` | `/api/v1/auth/me` | Bearer | Get current user info |
| `POST` | `/api/v1/locker/create` | Bearer | Create locker, returns locker_id + recovery_key |
| `POST` | `/api/v1/locker/unlock` | Bearer | Unlock with password, returns locker_token |
| `POST` | `/api/v1/locker/lock` | Bearer + X-Locker-Token | Manually lock locker |
| `GET` | `/api/v1/locker/status` | Bearer | Check if locker exists, if locked out |
| `POST` | `/api/v1/locker/change-password` | Bearer | Change locker password |
| `POST` | `/api/v1/locker/recover` | Bearer | Recover with recovery key |

### Frontend Implementation

| File | Purpose |
|------|---------|
| `Frontend/src/screens/LockerScreen.tsx` | Main Locker UI: Create / Unlock / Lock states, password input, error display |
| `Frontend/src/screens/LoginScreen.tsx` | Login screen with email/password + Google/Apple buttons |
| `Frontend/src/screens/SignUpScreen.tsx` | Registration screen |
| `Frontend/src/auth/AuthContext.tsx` | Global React context: `createLocker`, `unlockLocker`, `lockLocker`, `checkLocker`, 120s auto-lock timer |
| `Frontend/src/auth/authService.ts` | API client: all locker API calls, Bearer token management, `X-Locker-Token` header injection |
| `Frontend/src/auth/authStorage.ts` | In-memory session storage (token + locker token) |
| `Frontend/src/auth/authTypes.ts` | TypeScript types: `AuthUser`, `AuthSession`, `AuthState`, `AuthContextType` |
| `Frontend/src/config/apiConfig.ts` | API base URL configuration |
| `Frontend/src/types/index.ts` | App-wide TypeScript types including `Privacy`, `MemoryV1`, screen IDs |

### Authentication & Security

- Passwords stored as **Argon2id** hashes (never plaintext).
- Session tokens hashed with **SHA-256** before storage.
- Locker session automatically revoked after **120 seconds** of inactivity (server + client dual-enforcement).
- Bearer token required for all authenticated endpoints.
- `X-Locker-Token` required for all Private Locker memory access.
- Recovery key stored as Argon2id hash — shown to user **once only** at creation.
- `PRIVATE_LOCKER` memories cannot be shared to groups or other users.

### Database Dependencies

- Requires migrations `001`, `002`, `003` to run in order (see `003_auth_and_locker.sql`).
- Tables: `users`, `user_sessions`, `private_lockers`, `locker_sessions`
- Columns `owner_id`, `privacy` added to `raw_inputs` and `phase1_outputs`.

### Pipeline Integration

- Privacy flag `PRIVATE_LOCKER` is set during memory ingestion (Phase 1).
- `AuthorizationService.can_read_memory()` checks locker session validity before returning Phase 2 embedding results.
- The `locker_session_valid` flag is passed to Phase 2 vector search to include/exclude private memories.

### Tests

- `Tests/test_locker.py` — Unit tests for locker creation, unlock, lock, idle timeout, brute force lockout.
- `Tests/e2e_locker_test.py` — End-to-end locker integration tests against a running server.
- `Tests/conftest.py` — Shared pytest fixtures: in-memory SQLite test DB, auth dependency overrides.

---

## Component 2 — Groups System

### Purpose

The Groups System enables users to create named groups, manage members with role-based access (OWNER / ADMIN / MEMBER), share memories to groups, control access revocation, and comment on shared memories.

### Features Implemented

- **Group CRUD** — Create groups, list groups a user belongs to.
- **Member Management** — Add members (OWNER/ADMIN only), remove members.
- **Roles** — `OWNER`, `ADMIN`, `MEMBER` roles with enforced permission hierarchy.
- **Memory Sharing** — Share memories to groups (`MemoryGroupAccessModel`) or direct users (`MemoryUserAccessModel`).
- **Access Revocation** — Remove group or user access from shared memories.
- **Group Feed References** — `PUBLIC` memories shared to groups create feed references rather than ACL entries.
- **Authorization Service** — Unified `can_read_memory()` checks owner, public, group, and direct-share access.
- **Accessible Memory Query** — SQL subquery union for efficient filtering of accessible memories in Phase 2 search.
- **Comments** — Add, list, and delete comments on accessible memories.
- **Knowledge Eligible Comments** — Comments >4 words auto-derive a linked `Phase1Output` memory.
- **Comment Delete Sync** — Deleting a knowledge-eligible comment also removes its derived Phase1Output memory.

### Backend Implementation

| File | Purpose |
|------|---------|
| `Backend/app/api/routes/groups.py` | FastAPI routes: `POST /`, `GET /`, `POST /{id}/members`, `DELETE /{id}/members/{uid}` |
| `Backend/app/api/routes/comments.py` | `POST`, `GET`, `DELETE` for memory comments |
| `Backend/app/api/routes/auth.py` | User registration/login (shared dependency) |
| `Backend/app/services/group_service.py` | `GroupService`: create_group, add_member, remove_member with role enforcement |
| `Backend/app/services/share_service.py` | `ShareService`: share_memory, revoke_access with group/user ACL management |
| `Backend/app/services/authz_service.py` | `AuthorizationService`: can_read_memory, get_accessible_memory_ids_query |
| `Backend/app/services/comment_service.py` | `CommentService`: add_comment (with knowledge eligibility), delete_comment |
| `Backend/app/services/memory_search_service.py` | Phase 3 search respects group access via AuthorizationService |
| `Backend/app/services/auth_service.py` | User auth (shared dependency) |
| `Backend/app/database/models/groups.py` | `GroupModel`, `GroupMemberModel`, `MemoryGroupAccessModel`, `MemoryUserAccessModel`, `GroupFeedReferenceModel` |
| `Backend/app/database/models/comments.py` | `CommentModel` with knowledge eligibility flag |
| `Backend/app/database/models/user.py` | `UserModel`, `UserSessionModel` (shared dependency) |
| `Backend/app/database/models/base.py` | `Base`, `GUID` (shared dependency) |
| `Backend/app/database/connection/session.py` | DB session factory (shared dependency) |
| `Backend/app/database/migrations/004_groups_and_sharing.sql` | SQL schema: `groups`, `group_members`, `memory_group_access`, `memory_user_access`, `group_feed_references`, `comments` |
| `Backend/app/schemas/group.py` | `GroupCreateRequest`, `GroupResponse`, `AddMemberRequest`, `GroupMemberResponse` |
| `Backend/app/schemas/comment.py` | `CommentCreateRequest`, `CommentResponse` |
| `Backend/app/config.py` | App configuration (shared dependency) |
| `Backend/app/core/errors.py` | Error classes (shared dependency) |
| `Backend/app/core/enums.py` | Privacy enum (shared dependency) |

### API Endpoints

| Method | Route | Auth Required | Description |
|--------|-------|--------------|-------------|
| `POST` | `/api/v1/groups` | Bearer | Create a new group |
| `GET` | `/api/v1/groups` | Bearer | List groups the current user belongs to |
| `POST` | `/api/v1/groups/{group_id}/members` | Bearer | Add member (OWNER/ADMIN only) |
| `DELETE` | `/api/v1/groups/{group_id}/members/{user_id}` | Bearer | Remove member |
| `POST` | `/api/v1/memories/{memory_id}/comments` | Bearer | Add comment to memory |
| `GET` | `/api/v1/memories/{memory_id}/comments` | Bearer | List comments on memory |
| `DELETE` | `/api/v1/memories/{memory_id}/comments/{comment_id}` | Bearer | Delete comment (author only) |

### Frontend Implementation

| File | Purpose |
|------|---------|
| `Frontend/src/screens/GroupsScreen.tsx` | Groups screen UI — scaffold with FlatList (groups list UI is partially implemented) |

> **Implementation Note:** The `GroupsScreen.tsx` frontend is a scaffold-level implementation. The screen renders an empty groups list with a placeholder. Full group CRUD UI (create group form, member management, share memory to group) is not yet implemented in the frontend. The backend is fully implemented and testable.

### Roles & Permissions

| Role | Can Add Members | Can Remove Members | Can Remove Others |
|------|-----------------|--------------------|-------------------|
| `OWNER` | ✅ | ✅ | ✅ |
| `ADMIN` | ✅ | ✅ | ✅ |
| `MEMBER` | ❌ | ✅ (self only) | ❌ |

### Database Dependencies

- Requires migrations `001`–`004` to run in order (see `004_groups_and_sharing.sql`).
- Tables: `groups`, `group_members`, `memory_group_access`, `memory_user_access`, `group_feed_references`, `comments`.
- Columns `owning_group_id`, `source_type`, `parent_memory_id` added to `raw_inputs` and `phase1_outputs`.

### Pipeline Integration

- Groups integrate with Phase 2 vector search via `AuthorizationService.get_accessible_memory_ids_query()`.
- `memory_search_service.py` passes `locker_session_valid` and `user_id` to the repository, which applies group-aware ACL filtering.
- Comments link back to Phase 1 outputs via `derived_memory_id`.

### Tests

- `Tests/test_groups_e2e.py` — Basic group creation, member add, memory sharing, authorization check.
- `Tests/test_groups_full_e2e.py` — Comprehensive: group CRUD, roles, multi-group sharing, revocation, membership removal, public feed references, PRIVATE_LOCKER protection, comments + knowledge eligibility, delete sync.
- `Tests/conftest.py` — Shared pytest fixtures with in-memory SQLite.

---

## Technologies Used

### Backend
- **Python 3.11+**
- **FastAPI** ≥ 0.115
- **SQLAlchemy** ≥ 2.0 (async/await with `asyncpg`)
- **PostgreSQL** (production) / **SQLite** (testing)
- **passlib[argon2]** + **argon2-cffi** (password hashing)
- **pydantic-settings** (configuration)
- **pytest** + **pytest-asyncio** (testing)

### Frontend
- **React Native** 0.86.3
- **Expo** ~57
- **TypeScript** ~6.0.3
- **@expo/vector-icons** (Ionicons)

---

## Folder Structure

```
MindMesh_Parth_Contribution/
│
├── Private_Locker/
│   ├── Backend/
│   │   └── app/
│   │       ├── api/routes/locker.py, auth.py
│   │       ├── api/dependencies/auth.py
│   │       ├── services/locker_service.py, auth_service.py
│   │       ├── database/models/locker.py, user.py, base.py
│   │       ├── database/connection/session.py
│   │       ├── database/migrations/003_auth_and_locker.sql
│   │       ├── schemas/ (shared)
│   │       ├── core/ errors.py, logging.py, enums.py
│   │       └── config.py
│   ├── Frontend/
│   │   └── src/
│   │       ├── screens/LockerScreen.tsx, LoginScreen.tsx, SignUpScreen.tsx
│   │       ├── auth/AuthContext.tsx, authService.ts, authStorage.ts, authTypes.ts
│   │       ├── config/apiConfig.ts
│   │       └── types/index.ts
│   └── Tests/
│       ├── conftest.py
│       ├── test_locker.py
│       └── e2e_locker_test.py
│
├── Groups/
│   ├── Backend/
│   │   └── app/
│   │       ├── api/routes/groups.py, comments.py, auth.py
│   │       ├── services/group_service.py, share_service.py, authz_service.py
│   │       │           comment_service.py, memory_search_service.py, auth_service.py
│   │       ├── database/models/groups.py, comments.py, user.py, base.py
│   │       ├── database/connection/session.py
│   │       ├── database/migrations/004_groups_and_sharing.sql
│   │       ├── schemas/group.py, comment.py
│   │       ├── core/ errors.py, logging.py, enums.py
│   │       └── config.py
│   ├── Frontend/
│   │   └── src/screens/GroupsScreen.tsx
│   └── Tests/
│       ├── conftest.py
│       ├── test_groups_e2e.py
│       └── test_groups_full_e2e.py
│
├── README.md
├── FILE_MANIFEST.md
└── .gitignore
```

---

## Dependencies & Integration Limitations

Both components **require** the complete MindMesh application to run:

| Dependency | Used By | Notes |
|-----------|---------|-------|
| `raw_inputs` table | Both | Phase 1 ingestion pipeline |
| `phase1_outputs` table | Both | Phase 1 output storage |
| `phase2_embeddings` table | Groups (search) | Phase 2 vector search |
| `embedding_service.py` | Groups (search) | BAAI/bge-m3 model required |
| `llm_service.py` | Groups (search) | External LLM API required |
| `phase2_embedding_repo.py` | Groups (search) | pgvector repository |
| PostgreSQL + pgvector | Both | Production database |
| FastAPI app entrypoint (`main.py`) | Both | Router registration |

---

## Running / Testing

### Backend Tests (both components share the same test runner)

```bash
cd MindMesh-main/backend
pip install -e ".[dev]"
pytest tests/test_locker.py -v            # Private Locker unit tests
pytest tests/test_groups_e2e.py -v       # Groups basic e2e
pytest tests/test_groups_full_e2e.py -v  # Groups full e2e
```

Tests use an **in-memory SQLite database** — no PostgreSQL required for unit/integration tests.

### Frontend (React Native / Expo)

```bash
cd mindmesh-mobile
npm install
npx expo start
```

The Locker UI is fully functional. The Groups screen is a scaffold.

---

## Implementation Limitations

1. **Groups Frontend** — `GroupsScreen.tsx` is a placeholder (empty list). Group creation/management UI was not implemented in the frontend in this contribution scope.
2. **Google / Apple Sign-In** — `authService.ts` stubs for OAuth are not implemented (throw `Error` when called). Standard email/password auth is fully functional.
3. **Phase 2 Group Search** — `memory_search_service.py` is included as a dependency reference. The full Phase 2 embedding and retrieval pipeline requires PostgreSQL with pgvector and the BAAI/bge-m3 model — not included here.
4. **No Standalone Runtime** — Both components require the complete MindMesh application stack to run.
