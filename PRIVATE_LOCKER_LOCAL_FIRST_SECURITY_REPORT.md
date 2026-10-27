# MINDMESH — PRIVATE LOCKER LOCAL-FIRST SECURITY REPORT
**Date:** October 23, 2026  
**Security Architecture Classification:** Zero-Knowledge Cryptographic Isolation & Ephemeral Server Processing  
**Scope:** Separate Authentication Database, Local Device Key Management, Ephemeral AI Invariants & Zero-Persistence Audit

---

## 1. THREAT MODEL & SECURITY OBJECTIVES

The MindMesh Local-First Private Locker architecture was designed under the adversarial premise that the server database or network transport could be compromised. Private content must remain confidential even against:
1. **Compromised Server Database:** A database dump of the primary `mindmesh_db` or the auth database `mindmesh_locker_auth` must reveal ZERO plaintext memories, photos, audio files, or vector embeddings.
2. **Untrusted Infrastructure:** Server-side logs, disk storage, and caches must never retain unencrypted private data.
3. **Cross-Tenant Leakage:** A user querying memories or semantic vectors must never receive another user's private data, nor should private snippets ever be included in group feeds or public searches.

---

## 2. SEPARATE AUTHENTICATION DATABASE (`mindmesh_locker_auth`)

### Architectural Isolation:
- **Connection Separation:** Governed by `app/local_first/database.py`, using a distinct connection URL (`LOCKER_AUTH_DATABASE_URL`).
- **Entity Independence:** Uses an isolated declarative base (`LockerAuthBase`), completely decoupled from `UserModel` or `raw_inputs`.
- **Pseudonymous References:** Users are identified via a SHA-256 HMAC pseudonym (`user_reference`), breaking foreign-key linkage with the primary application user database.

### Schema Fields & Allowed Information:
- `id` (UUIDv4 primary key)
- `user_reference` (Pseudonymous reference hash)
- `argon2_hash` (Argon2id password verifier: memory cost 64MB, 3 iterations)
- `recovery_hash` (Argon2id verifier for 32-character recovery key)
- `failed_attempts` (Counter for brute-force mitigation)
- `lockout_until` (Timestamp for progressive or 5-attempt lockouts)
- `created_at` / `updated_at` (Audit timestamps)

### Prohibited Information (Strictly Enforced):
- Plaintext passwords or encryption keys (PROHIBITED)
- User memories, texts, summaries, or entities (PROHIBITED)
- User photos, audio recordings, or media references (PROHIBITED)
- Vector embeddings or search indexes (PROHIBITED)
- Plaintext recovery keys (PROHIBITED)

---

## 3. PHONE-LOCAL ENCRYPTED STORAGE & KEY MANAGEMENT

### Cryptographic Hierarchy:
1. **Data Encryption Key (DEK):**
   - 256-bit high-entropy key generated on the device using cryptographically secure random bytes (`crypto.getRandomValues`).
   - Used exclusively to encrypt/decrypt local records and local embeddings using AES-256-GCM.
2. **Master Key (KEK - Key Encryption Key):**
   - Derived from the user's unlock password using PBKDF2 with SHA-256 and a random 16-byte salt (100,000 iterations).
   - Used solely to wrap (encrypt) the DEK into a `WrappedKeyEnvelope`.
3. **Key Envelope at Rest:**
   - Contains: `{ salt, nonce, wrappedKey, authTag, iterations }`.
   - Stored in app-private storage. Even if raw device files are extracted, the DEK cannot be decrypted without the user's password.
4. **Transient In-Memory Lifecycle:**
   - When the user unlocks the locker, the DEK is unwrapped and held in transient memory.
   - On lock, backgrounding, or logout, memory references are zeroized.

### Encrypted Backup & Device-Loss Recovery:
- Users can export an encrypted archive (`EncryptedBackupArchive`) protected by an independent backup passphrase.
- In the event of device loss, the backup archive can be restored onto a new device by providing the backup passphrase.
- **Forgotten Password Limitation:** If the user forgets both their unlock password and loses their recovery key, private data CANNOT be decrypted. There is no server backdoor.

---

## 4. CONSENT-BASED EPHEMERAL AI PROCESSING

When the user requests AI extraction, embedding generation, or question answering:
1. **Explicit Consent Modal (`ConsentGate.tsx`):**
   - Displays exact text preview to be sent.
   - Displays intended purpose (`semantic_extraction`, `embedding_generation`, `question_answering`).
   - Requires explicit tap on "Authorize AI Processing". Consent is NEVER pre-selected.
2. **Zero-Persistence Verification (`temporary_processing.py`):**
   - Requests are processed in transient server RAM.
   - Handled directly by `EphemeralAiService`.
   - Automated tests in `test_local_first_auth.py` strictly asserted:
     - `raw_inputs` table contained ZERO occurrences of the private snippet.
     - `phase1_outputs` table contained ZERO occurrences of the private snippet.
     - `phase2_embeddings` table received ZERO vector records.
   - Ephemeral buffers are discarded immediately following the HTTP response.

---

## 5. AUTOMATED SECURITY TEST MATRIX

| Security Requirement | Test Suite | Verification Method | Verdict |
| :--- | :--- | :--- | :--- |
| **Argon2id Verifier Storage** | `test_local_first_auth.py` | Verified password hash is salted Argon2id format; no plaintext | **PASS** |
| **5-Attempt Lockout** | `test_local_first_auth.py` | Attempted 5 incorrect passwords; verified 6th attempt returns 403 Locked Out | **PASS** |
| **Recovery Key Rotation** | `test_local_first_auth.py` | Used recovery key to rotate password; verified old recovery key is revoked | **PASS** |
| **120s Session Timeout** | `test_local_first_auth.py` | Verified session expires after inactivity | **PASS** |
| **Session Revocation** | `test_local_first_auth.py` | Verified calling `/lock` invalidates session token immediately | **PASS** |
| **Zero Server Persistence** | `test_local_first_auth.py` | Database scan over `raw_inputs`, `phase1_outputs`, `phase2_embeddings` | **PASS** |
| **AES-256-GCM Encryption** | `test_locker_22_security_audit.py` | Verified ciphertext structure with `enc:v1:` prefix and 96-bit nonce | **PASS** |
| **Phase 2 Ciphertext Fix** | `test_locker.py` | Verified embeddings generated from decrypted plaintext in RAM, never ciphertext | **PASS** |
| **Cross-User Isolation** | `test_locker.py` | User B search cannot retrieve User A private records | **PASS** |
| **Feed Isolation** | `test_locker.py` | Locked user cannot see Private Locker records in `/feed` | **PASS** |
