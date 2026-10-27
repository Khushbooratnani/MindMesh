# MINDMESH — PACKAGE B SECURITY VERIFICATION REPORT

**Evaluation Date:** October 23, 2026  
**Auditor:** Principal Software Architect & Application Security Auditor  
**Scope:** Cryptographic Hierarchy, Isolated Authentication Database, Local Encrypted Storage, Ephemeral AI Invariants, and Zero-Persistence Verification  
**Classification:** Confidential Security Evaluation  

---

## 1. THREAT MODEL & SECURITY OBJECTIVES

The MindMesh Local-First Private Locker architecture was engineered to defend private user memories against compromised server infrastructure, database leaks, and untrusted network transport:

1. **Compromised Server Database:** A complete dump of PostgreSQL databases `mindmesh` or `mindmesh_copy` or `mindmesh_locker_auth` reveals **zero** private memory text, voice recordings, photos, or vector embeddings.
2. **Untrusted AI Processing:** Server-side ephemeral AI endpoints process memories strictly in volatile RAM and immediately discard intermediate buffers upon completing the request.
3. **Cross-Tenant Leakage:** Private records stored locally on Device A cannot be indexed, queried, or retrieved by User B.

---

## 2. CRYPTOGRAPHIC ARCHITECTURE & KEY MANAGEMENT

### 2.1. Dual-Tier Key Hierarchy
1. **Data Encryption Key (DEK):**
   - 256-bit cryptographically secure symmetric key generated on the client device using `crypto.getRandomValues`.
   - Used exclusively to encrypt/decrypt local records and local embeddings using AES-256-GCM.
2. **Key Encryption Key (Master KEK):**
   - Derived from user's unlock password using PBKDF2 with SHA-256, 16-byte random salt, and 100,000 iterations.
   - Used solely to wrap the DEK into a `WrappedKeyEnvelope`.
3. **Key Envelope at Rest:**
   - Stored in application-private storage as `{ salt, nonce, wrappedKey, authTag, iterations }`.
   - The DEK cannot be decrypted without the user's password.
4. **Volatile Memory Lifecycle & Zeroization:**
   - On unlock, the DEK is unwrapped and held in transient memory.
   - On lock, backgrounding, or logout, memory references are actively cleared (`zeroize()`).

---

## 3. SEPARATE AUTHENTICATION DATABASE ISOLATION

### 3.1. Architectural Isolation
- **Target:** PostgreSQL database `mindmesh_locker_auth` on `localhost:5432`.
- **Entity Independence:** Governed by `app/local_first/models.py` using `LockerAuthBase`, decoupled from `UserModel` or `RawInputModel`.
- **Pseudonymous References:** Users are identified via a SHA-256 HMAC pseudonym (`user_reference`), breaking foreign-key linkage with the primary application user database.

### 3.2. Prohibited vs Allowed Information
- **Allowed:** Pseudonymous user reference, Argon2id password verifier (64MB memory cost, 3 iterations), recovery key Argon2id verifier, failed attempt counter, lockout timestamp, session token hash.
- **Strictly Prohibited & Verified Absent:**
  - Plaintext passwords or encryption keys (Absent)
  - User memories, texts, summaries, or entities (Absent)
  - Photos, audio recordings, or media references (Absent)
  - Vector embeddings or search indexes (Absent)
  - Plaintext recovery keys (Absent)

---

## 4. CONSENT-BASED EPHEMERAL AI PROCESSING & ZERO PERSISTENCE

### 4.1. Explicit Consent Gate (`ConsentGate.tsx`)
- Displays exact text preview before dispatch.
- Displays declared purpose (`semantic_extraction`, `embedding_generation`, `question_answering`).
- Requires explicit user tap; consent is **never** pre-selected.
- Cancel button immediately aborts transmission.

### 4.2. Zero-Persistence Verification
Automated assertions in `test_local_first_auth.py` verified that processing ephemeral AI requests leaves zero residual footprint:
- Scan over PostgreSQL `raw_inputs`: **0 records created**.
- Scan over PostgreSQL `phase1_outputs`: **0 records created**.
- Scan over PostgreSQL `phase2_embeddings`: **0 records created**.
- Ephemeral response payloads return directly to the caller.

---

## 5. RECOVERY LIMITATIONS & DEVICE LOSS

- **Recovery Credential:** Users receive a 32-character recovery key (`rcv_...`) during initial setup.
- **Key Rotation:** Using the recovery key allows resetting the password and automatically revokes all previous sessions and rotates the recovery key.
- **Zero-Backdoor Principle:** If a user loses both their password and recovery key, private data cannot be decrypted by MindMesh administrators or server operators.

---

## 6. DEVICE SECURITY SUMMARY

| Control | Implementation | Verification Method | Status |
| :--- | :--- | :--- | :---: |
| **Argon2id Verifier Storage** | `service.py` | Automated pytest | **PASS** |
| **5-Attempt Lockout** | `service.py` | 5 failed attempts -> 6th locked out | **PASS** |
| **Recovery Key Rotation** | `service.py` | Old key revoked upon use | **PASS** |
| **120s Session Timeout** | `service.py` | Inactivity window enforcement | **PASS** |
| **Session Revocation** | `routes.py` (`POST /lock`) | Token invalidated immediately | **PASS** |
| **Zero Server Persistence** | `test_local_first_auth.py` | Scanned `raw_inputs`, `phase1`, `phase2` | **PASS** |
| **Local AES-256-GCM** | `localEncryptedStorage.ts` | Authenticated encryption | **PASS** |
| **Local Cosine Vector Search** | `localEncryptedStorage.ts` | 1024-dim similarity ranking | **PASS** |
