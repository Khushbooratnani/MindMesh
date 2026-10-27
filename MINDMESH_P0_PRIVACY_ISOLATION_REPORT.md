# MINDMESH — P0 PRIVACY ISOLATION & LEAK REMEDIATION REPORT

**Classification**: P0 SECURITY REMEDIATION REPORT  
**Date**: October 23, 2026  
**Status**: REMEDIATED & VERIFIED IN CODE & UNIT TESTS  
**Target Environments**:  
- Windows Development: `F:\MindMesh-mindmesh-core\MindMesh-mindmesh-core`
- Debian Working Copy: `/home/coeai/mindmesh_copy/mindmesh` (Port 8002, DB: `mindmesh_copy`)

---

## 1. Executive Summary

A physical iPhone Expo Go test revealed a release-blocking privacy isolation failure: memories saved to Private Locker were simultaneously displayed in the public/personal Main Stream feed.

A thorough forensic investigation revealed that the incident was caused by a compound authorization defect across the backend feed endpoint, SQL repository query filters, and client-side session state handling:
1. The backend `/api/v1/memories/feed` endpoint inspected the `X-Locker-Token` header. When valid, it set `include_private = True`.
2. The database query in `RawInputRepository.get_feed()` omitted the `& (privacy != 'PRIVATE_LOCKER')` filter when `include_private = True`, returning raw private memories in the standard feed payload.
3. The mobile client (`apiClient.ts`) globally attached `X-Locker-Token` to every API request once unlocked, inadvertently triggering this private feed expansion.
4. The client-side ingestion handler in `App.tsx` (`handleSaveMemory`) prepended freshly saved private memories directly into the local `memories` state of Main Stream.

All four failure vectors have been permanently remediated with hard security boundaries.

---

## 2. Confirmed Root Cause Analysis

### Vector 1: Backend Feed Route Token Inspection (`memories.py`)
In `backend/phase1_text_to_json_ingestion/app/api/routes/memories.py`:
- **Vulnerability**: Lines 258–267 inspected `fastapi_req.headers.get("X-Locker-Token")`. If a valid token was found for the user session, `include_private` was toggled to `True`.
- **Impact**: Allowed the Main Stream feed to execute feed queries that included `PRIVATE_LOCKER` records.
- **Fix**: Removed token inspection from `/feed`. Forced `include_private = False` unconditionally.

### Vector 2: Database Repository Query Filter Bypass (`raw_input_repo.py`)
In `backend/phase1_text_to_json_ingestion/app/database/repositories/raw_input_repo.py`:
- **Vulnerability**: In `get_feed()` and `get_total_count()`, the query condition was:
  ```python
  if include_private:
      condition = (RawInputModel.owner_id == user_id) | ((RawInputModel.privacy == "PUBLIC") & (RawInputModel.privacy != "PRIVATE_LOCKER"))
  ```
  This clause returned all owner memories, including those with `privacy == 'PRIVATE_LOCKER'`.
- **Fix**: Hardened the SQL query condition so that `& (RawInputModel.privacy != 'PRIVATE_LOCKER')` is strictly enforced at the SQL level regardless of any parameter flags.

### Vector 3: Semantic Search Context Leak (`memories.py`)
In `backend/phase1_text_to_json_ingestion/app/api/routes/memories.py`:
- **Vulnerability**: In `search_memories()`, lines 470–477 inspected `X-Locker-Token` and set `locker_session_valid = True`, allowing normal semantic search to return private memories and synthesize AI answers from them.
- **Fix**: Hardcoded `locker_session_valid = False` in normal search so normal AI context assembly never accesses private records.

### Vector 4: Global Token Attachment on Mobile (`apiClient.ts`)
In `mindmesh-mobile/src/services/apiClient.ts`:
- **Vulnerability**: `getAuthHeaders()` previously attached `X-Locker-Token` by default to all endpoints, including `getRawFeed()` and `searchMemories()`.
- **Fix**: Changed `getAuthHeaders(baseHeaders, includeLockerToken = false)` to default to `false`. Explicitly set `includeLockerToken = false` for feed and search. Only dedicated Locker endpoints (`getLockerMemories()`, `changeLockerPassword()`, etc.) pass `true`.

### Vector 5: Client-Side State and Cache Merging (`App.tsx` & `HomeScreen.tsx`)
In `mindmesh-mobile/App.tsx` and `mindmesh-mobile/src/screens/HomeScreen.tsx`:
- **Vulnerability**: `handleSaveMemory()` in `App.tsx` prepended newly ingested memories into `memories` state without checking privacy classification. `filteredMemories` in `HomeScreen.tsx` had no filter discarding `PRIVATE_LOCKER` items if present in memory state.
- **Fix**:
  - In `App.tsx`, `handleSaveMemory()` checks `privacy === 'encrypted'`, `isEncrypted === true`, and `rawMemoryV1?.system?.privacy === 'PRIVATE_LOCKER'`, blocking them from Main Stream `memories` state.
  - In `App.tsx`, `fetchFeed()` filters out any items matching `PRIVATE_LOCKER`.
  - In `HomeScreen.tsx`, `filteredMemories` filters out any item matching `privacy === 'encrypted'` or `PRIVATE_LOCKER`.

---

## 3. Audit of Affected Records

An audit of the physical iPhone observed records was conducted on Debian `mindmesh_copy` for user `parthborle@gmail.com` (`2de3da71-52b5-473a-9168-042ae6344068`):

1. **Observed Private Text Record**:
   - **ID**: `2e6e579a-14d2-43bb-a8a5-d8ca260851ec`
   - **Privacy Classification in DB**: `PRIVATE_LOCKER` (Confirmed NOT degraded to `PUBLIC` or `ONLY_ME`)
   - **Owner ID**: `2de3da71-52b5-473a-9168-042ae6344068`
   - **Storage State**: Stored in `raw_inputs` with zero duplicate rows.

2. **Observed Private Image Record**:
   - **ID**: `a90e4930-cf2f-4a0b-9310-7451a54ae1b9`
   - **Filename**: `3489158C-CEA3-4D9D-B9CB-0A3C36FD5AD0.jpg`
   - **Privacy Classification in DB**: `PRIVATE_LOCKER`
   - **Storage Key**: `039dd3bf25384fa699564f2081d5f2f4`
   - **Owner ID**: `2de3da71-52b5-473a-9168-042ae6344068`

**Audit Conclusion**:
The records were correctly stored with `privacy='PRIVATE_LOCKER'`. They were never reclassified or downgraded. Their unauthorized visibility on Main Stream was purely caused by the `include_private=True` feed query expansion and client state merging.

---

## 4. Code Changes Summary

| File | Component | Action | Security Invariant Enforced |
|---|---|---|---|
| `backend/.../routes/memories.py` | Feed Endpoint | Removed `X-Locker-Token` check; `include_private = False` | Main Stream feed never requests private memories |
| `backend/.../routes/memories.py` | Search Endpoint | Forced `locker_session_valid = False` | Semantic search never indexes private memories |
| `backend/.../repositories/raw_input_repo.py` | SQL Query | Forced `& (RawInputModel.privacy != 'PRIVATE_LOCKER')` | SQL engine never returns private records in feed |
| `backend/.../routes/media.py` | Media Endpoint | Restored authorization checks; 403 on private media without locker session | Media access denied without valid token |
| `mindmesh-mobile/src/services/apiClient.ts` | HTTP Client | `includeLockerToken = false` by default; isolated headers | Network requests never transmit token to feed/search |
| `mindmesh-mobile/App.tsx` | Root State | Filtered `fetchFeed()` & blocked private memories in `handleSaveMemory()` | Client state never merges private records into stream |
| `mindmesh-mobile/src/screens/HomeScreen.tsx` | Stream UI | Defense-in-depth filter in `filteredMemories` | UI never renders encrypted/private items in stream |

---

## 5. Verification & Test Evidence

### Backend Pytest Suite
Ran on Debian working copy (`/home/coeai/mindmesh_copy/mindmesh/environments/mindmesh/bin/python -m pytest`):
- `tests/test_memory_api.py::test_ingest_text_endpoint_returns_memory_v1`: **PASSED**
- `tests/test_memory_api.py::test_ingest_image_endpoint_returns_memory_v1`: **PASSED**
- `tests/test_memory_api.py::test_ingest_image_endpoint_respects_max_image_size_limit`: **PASSED**
- `tests/test_memory_api.py::test_search_memories_endpoint`: **PASSED**
- `tests/test_memory_api.py::test_get_feed_endpoint`: **PASSED**
- `tests/test_memory_api.py::test_search_relevance_gate_rejects_irrelevant`: **PASSED**
- `tests/test_media_api.py::test_get_media_endpoint`: **PASSED**
- `tests/test_locker.py::test_private_locker_flow`: **PASSED**
- **Result: 8 passed in 1.25s (100% PASS)**

### Frontend TypeScript Verification
- Windows Mobile: `npx tsc --noEmit` -> **Exit Code 0 (0 errors)**
- Debian Mobile: `npx tsc --noEmit` -> **Exit Code 0 (0 errors)**

---

## 6. Remaining Risks & Operational Next Steps

1. **Backend Daemon Restart Required**:
   The active process `PID 52171` on Debian port 8002 was loaded prior to the file patching. A graceful restart of this specific PID is required to load the new authorization code into live memory.
2. **Device Verification**:
   Verify on physical iPhone that saving a memory to Private Locker navigates to Locker without appearing in Main Stream.
