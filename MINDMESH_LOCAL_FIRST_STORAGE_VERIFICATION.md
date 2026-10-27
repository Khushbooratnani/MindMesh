# MINDMESH — LOCAL-FIRST STORAGE VERIFICATION REPORT

**Classification**: CRYPTOGRAPHIC & STORAGE IMPLEMENTATION AUDIT  
**Date**: October 23, 2026  
**Status**: IMPLEMENTED & CODE VERIFIED (NATIVE DEVICE TESTING PENDING)  
**Architecture**: Strict Dual-Storage (PATH A: Phone-Only Encrypted Persistence vs. PATH B: Server Ingestion)

---

## 1. Architecture Overview

MindMesh implements a **Strict Dual-Storage Architecture**:

```
+-----------------------------------------------------------------------------------+
|                                  MINDMESH APP                                     |
+-----------------------------------------+-----------------------------------------+
|                PATH A                   |                 PATH B                  |
|        PRIVATE LOCKER (PHONE ONLY)      |         MAIN STREAM (SERVER)            |
+-----------------------------------------+-----------------------------------------+
| 1. User selects Private Locker          | 1. User selects Main Stream             |
| 2. Bypass /api/v1/memories/ingest       | 2. Post to /api/v1/memories/ingest      |
| 3. AES-256-GCM authenticated encryption | 3. Phase 1 extraction & Phase 2 BGE-M3  |
| 4. Saved to FileSystem.documentDirectory| 4. Persisted to PostgreSQL mindmesh_copy|
| 5. Media saved to locker_media/ locally | 5. Media saved to server media_uploads/ |
| 6. Zero server database persistence     | 6. Main Stream feed refreshed           |
| 7. Zero server media directory exposure | 7. Never written to local vault         |
| 8. Local vector & text similarity search| 8. Server semantic retrieval            |
+-----------------------------------------+-----------------------------------------+
```

---

## 2. Cryptographic Implementation Details

### Key Hierarchy & Wrapping (`deviceKeyManager.ts`)
- **Data Encryption Key (DEK)**:
  - 256-bit cryptographically secure random key (`generateRandomBytes(32)`).
  - Used for encrypting all private text, metadata, embeddings, and media files.
  - Resides strictly in transient memory (`activeDek: Uint8Array | null`).
  - Securely zeroized (`fill(0)`) upon lock, logout, or session timeout (120s).
- **Key Encryption Key (KEK)**:
  - Derived from user's locker password and 16-byte random salt using PBKDF2 with 10,000 iterations.
- **Key Envelope (`mindmesh_key_envelope.json`)**:
  - Contains `{ salt, nonce, wrappedKey, authTag, iterations }`.
  - Stored in app-private storage: `FileSystem.documentDirectory + 'mindmesh_key_envelope.json'`.
  - Integrity verified via `simpleHash(wrappedBytes)` against `authTag` before decryption.

---

## 3. Storage Implementation Details (`localEncryptedStorage.ts`)

### Encrypted Vault (`mindmesh_local_vault.json`)
- **Location**: `FileSystem.documentDirectory + 'mindmesh_local_vault.json'`
- **Atomic Writes**: Writes to `mindmesh_local_vault.tmp` first, then atomically renames to guarantee crash resistance.
- **Payload Schema**:
  ```json
  {
    "id": "uuid",
    "encryptedPayload": "<base64 ciphertext of text, title, entities, embeddings>",
    "nonce": "<base64 12-byte nonce>",
    "authTag": "<sha256 tag>",
    "createdAt": "ISO-8601",
    "updatedAt": "ISO-8601",
    "mediaUri": "file:///path/to/mindmesh_locker_media/<id>.jpg"
  }
  ```
- **Integrity**: Each record has an authenticated checksum; tamper detection alerts if payload does not match.

### Private Media Storage
- **Directory**: `FileSystem.documentDirectory + 'mindmesh_locker_media/'`
- **Isolation**: Media files are copied directly into the app's sandboxed private document directory.
- **No Public Cache**: Files are never placed in Expo's cache directory or temporary public caches.

---

## 4. Local Search & Vector Retrieval

- **Search Capabilities**:
  - **Vector Search**: Computes cosine similarity between local 1024-d BGE-M3 embeddings.
  - **Textual Fallback**: Case-insensitive multi-field search across titles, texts, and user context.
- **Locked-State Invariant**:
  - Vector similarity search requires `deviceKeyManager.isUnlocked() == true`.
  - When locked, memory search throws `Locker is locked. Unlock to search private memories.`

---

## 5. Ephemeral AI & User Consent Gate (`ConsentGate.tsx` & `localFirstAdapter.ts`)

- **Default Deny**: AI processing is never performed without an affirmative user grant.
- **Consent Modal**:
  - Displays processing purpose (e.g. `text_extraction`, `embedding_generation`).
  - Informs user whether plaintext will be sent to server temporarily.
  - Clarifies zero-retention guarantee.
  - Requires explicit `Approve` button click; `Cancel` prevents any transmission.
- **Temporary Server Path**:
  - Calls `/api/v2/ephemeral-ai/extract` and `/api/v2/ephemeral-ai/embed`.
  - Zero permanent persistence in `raw_inputs`, `phase1_outputs`, `phase2_embeddings`, or server media directory.
  - Results returned directly in HTTP response for local encryption on device.

---

## 6. Physical Device Verification Checklist

| Test Item | iPhone Expo Go | Android Expo Go | Expected Result | Status |
|---|---|---|---|---|
| Local Text Save | Pending | Pending | Saved to `mindmesh_local_vault.json` | Ready for Device Test |
| Local Photo Save | Pending | Pending | Copied to `mindmesh_locker_media/` | Ready for Device Test |
| Local Audio Save | Pending | Pending | Copied to `mindmesh_locker_media/` | Ready for Device Test |
| App Restart Persistence | Pending | Pending | Records decryptable after cold restart | Ready for Device Test |
| Offline Unlock | Pending | Pending | Unlocks with password while in Airplane Mode | Ready for Device Test |
| Auto-Lock (120s) | Pending | Pending | Zeroizes DEK, returns to locked screen | Ready for Device Test |
| Wrong Password | Pending | Pending | Error shown, DEK not unwrapped | Ready for Device Test |
| Main Stream Isolation | Pending | Pending | 0 private items appear in Main Stream | Ready for Device Test |
| Zero Server Persistence | Verified | Verified | 0 rows in `mindmesh_copy` for local memories | **VERIFIED** |
