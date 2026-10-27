# MINDMESH — PRIVATE LOCKER CUTOVER READINESS REPORT

**Classification**: DEPLOYMENT & READINESS AUDIT  
**Date**: October 23, 2026  
**Status**: CONTROLLED CUTOVER STAGED — AWAITING RESTART APPROVAL  

---

## 1. Package A Regression Status

| Component | Test Suite | Result | Details |
|---|---|---|---|
| Ingestion API (Text) | `test_ingest_text_endpoint_returns_memory_v1` | **PASSED** | Normal ingestion produces canonical MemoryV1 |
| Ingestion API (Image) | `test_ingest_image_endpoint_returns_memory_v1` | **PASSED** | Normal image upload & size constraints verified |
| Feed API | `test_get_feed_endpoint` | **PASSED** | Normal feed excludes `PRIVATE_LOCKER` |
| Search API | `test_search_memories_endpoint` | **PASSED** | Normal search excludes `PRIVATE_LOCKER` |
| Media API | `test_get_media_endpoint` | **PASSED** | Media serving authorized correctly |
| Package A Locker | `test_private_locker_flow` | **PASSED** | Legacy server locker lifecycle intact |
| TypeScript Types | `npx tsc --noEmit` | **PASSED** | Zero errors on Windows & Debian |

---

## 2. Package B Local-First Readiness

- **Device Key Management**: Fully implemented in `deviceKeyManager.ts` with PBKDF2/AES key wrapping and envelope persistence in app-private storage.
- **Local Persistence**: Fully implemented in `localEncryptedStorage.ts` with atomic writes, checksum verification, and local media isolation.
- **Storage Adapter**: Strict separation in `ComposerScreen.tsx` (PATH A: Private Locker -> Device-Only; PATH B: Main Stream -> Server Ingestion).
- **Backend Isolation**: Experimental `/api/v2/locker-auth` and `/api/v2/ephemeral-ai` remain gated behind feature flags (`enable_local_first_locker = False`, empty test-user allowlist).

---

## 3. Existing Legacy Data Migration Plan

Existing legacy private memories currently reside in the Debian `mindmesh_copy` database under `raw_inputs` (`privacy = 'PRIVATE_LOCKER'`).

### Migration Steps:
1. **User Authentication**: User logs into MindMesh.
2. **Locker Unlock**: User provides password; client authenticates against server locker endpoint.
3. **Download Authorized Records**: Client fetches legacy records via `/api/v1/locker/memories`.
4. **Local Encrypted Storage**: Client re-encrypts each record using the local DEK and writes to `mindmesh_local_vault.json`.
5. **Integrity & Count Verification**: Verify that the number of locally stored items matches server records.
6. **Offline Access Confirmation**: User verifies they can view all memories in Private Locker while in Airplane Mode.
7. **Deletion Approval Gate**: Only after explicit user approval, submit a proposal to purge legacy server rows from `mindmesh_copy`.

> **CRITICAL POLICY**: Zero legacy records have been deleted or modified. They will remain intact on Debian until explicit user approval for migration is given.

---

## 4. Required Approvals & Cutover Checklist

| Gate | Action | Risk Level | Status |
|---|---|---|---|
| **Gate 1** | Graceful restart of backend daemon on Debian port 8002 (`PID 52171`) to activate query isolation | **Low** (Safe restart of working copy) | **AWAITING USER APPROVAL** |
| **Gate 2** | Physical iPhone end-to-end verification of Private Locker vs Main Stream | **None** (Read/write on test device) | Pending Gate 1 |
| **Gate 3** | Package B backend flag enablement (`enable_local_first_locker = True`) | **Medium** (Enables `/api/v2/` routes) | Blocked until Gate 2 passes |
| **Gate 4** | Legacy server data purge/migration | **High** (Data modification) | Blocked until Gate 2 & 3 pass |

---

## 5. Activation Recommendation

1. **Approve Gate 1**: Restart ONLY the working-copy backend daemon on port 8002.
2. **Perform Manual Device Test**:
   - Open MindMesh on physical iPhone (Expo Go).
   - Ingest a memory with "Private Locker" selected.
   - Verify that the memory appears **only** in Private Locker with the "On-Device" badge and **never** in Main Stream.
3. **Confirm Zero Persistence**:
   - Query Debian `mindmesh_copy` to verify 0 new rows were created in `raw_inputs`.
