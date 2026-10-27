# Package B Test-User Security Readiness Report

**Date:** 2026-10-23  
**Status:** INTEGRATED & GUARDED — READY FOR ISOLATED APPROVAL  
**Feature Flags:** Backend `enable_local_first_locker = False` | Mobile `USE_LOCAL_FIRST_LOCKER = false`  
**Allowlist Status:** Default Deny (`local_first_test_user_allowlist = []`)  

---

## 1. Architecture & Security Invariants

Package B provides an experimental Local-First Private Locker architecture wherein:
1. Private text, media, and embeddings are stored encrypted on the user's mobile device using AES-256-GCM.
2. The server-side authentication database (`mindmesh_locker_auth`) stores ONLY Argon2id password verifiers, salt, key-derivation parameters, and rate-limiting lockout state.
3. Server-side Ephemeral AI routes (`/api/v2/ephemeral-ai/*`) operate with zero server persistence, handling strictly consented in-memory extraction and vector embeddings that are immediately discarded after the HTTP response.
4. Core Package A database (`mindmesh_copy` on port 8002) is completely isolated from Package B operations.

---

## 2. Server-Enforced Test-User Allowlist

To prevent unauthorized exposure of experimental endpoints to general users, a dual-layer security gate has been implemented on the backend:

### 2.1 Configuration Layer (`app/config.py`)
```python
# Package B Local-First Private Locker Configuration (Feature-Gated & Secure Allowlist)
enable_local_first_locker: bool = False
locker_auth_database_url: str = "postgresql+asyncpg://coeai@localhost:5432/mindmesh_locker_auth"
local_first_test_user_allowlist: list[str] = []
```

### 2.2 Route Guard Dependency (`app/main.py`)
```python
async def verify_local_first_access(current_user: UserModel = Depends(get_current_user)):
    """
    Server-enforced allowlist gate for experimental Package B routes:
    1. Global feature flag must be enabled.
    2. Server-side allowlist check (default deny): The authenticated user ID from JWT
       must be explicitly listed in settings.local_first_test_user_allowlist.
    """
    if not getattr(settings, "enable_local_first_locker", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local-First Private Locker feature is disabled by default.",
        )
    allowlist = getattr(settings, "local_first_test_user_allowlist", [])
    if not allowlist or current_user.id not in allowlist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized for experimental Local-First Private Locker features.",
        )

app.include_router(local_first_auth_router, dependencies=[Depends(verify_local_first_access)])
app.include_router(ephemeral_ai_router, dependencies=[Depends(verify_local_first_access)])
```

### 2.3 Security Guarantees
- **Default Deny**: When `local_first_test_user_allowlist` is empty (`[]`), all requests receive HTTP 403 Forbidden.
- **Cryptographic User Identity**: User identity is verified from the server-validated JWT Bearer token (`current_user.id`). Client-supplied user IDs in query parameters or request bodies are ignored.
- **Universal Route Protection**: Applied to all `/api/v2/locker-auth/*` and `/api/v2/ephemeral-ai/*` routes.
- **Automated Test Verification**: `tests/test_local_first_auth.py` tests both default-deny (HTTP 403) and authorized allowlisted access (HTTP 200). Passed 100% on Debian backend.

---

## 3. Database Isolation Verification

- **Working-Copy Database**: `mindmesh_copy` (PostgreSQL on port 5432) manages Package A memories, users, and sessions.
- **Locker Auth Database**: `mindmesh_locker_auth` (PostgreSQL on port 5432) manages only `local_first_locker_identities` and `local_first_locker_sessions`.
- **Zero Cross-Contamination**: Neither database has foreign keys or references to the other.

---

## 4. Mobile Hardware & Runtime Requirements

### 4.1 Expo Go Constraints
- Expo Go provides managed JavaScript runtime environment. High-assurance hardware-backed keystores (iOS Secure Enclave via Keychain `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` / Android Hardware Keystore) require native modules that cannot be bundled dynamically into standard Expo Go.
- `src/local_first/deviceKeyManager.ts` and `localEncryptedStorage.ts` implement standards-compliant WebCrypto/Software PBKDF2/AES-GCM for dev testing.

### 4.2 Native Development Build Path
- For production-grade hardware security, an EAS Development Build (`npx expo run:ios` / `npx expo run:android`) with `expo-secure-store` and hardware-backed JSI cryptography is prepared.
- Hardware-backed security claims will only be certified following testing on a native standalone development build.

---

## 5. Controlled Activation Procedure

To activate Package B for an isolated test user, the following approval-gated steps must be performed:
1. User provides explicit approval to enable Package B for specific test account UUIDs.
2. Add approved test account UUIDs to `local_first_test_user_allowlist` in `.env` or `config.py`.
3. Set `enable_local_first_locker = True` on backend and restart port 8002 daemon.
4. Set `USE_LOCAL_FIRST_LOCKER = true` in mobile `src/config/apiConfig.ts`.
5. Execute isolated validation on physical test device.
