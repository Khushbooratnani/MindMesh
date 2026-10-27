import base64
import io
import json
import time
import uuid
import httpx

BASE_URL = "http://127.0.0.1:8002"
ts = int(time.time())
TEST_USER = f"deploy_test_{ts}"
TEST_PASS = "TestPass123!Safe"
LOCKER_PASS = "LockerSecurePass123!"

# Valid 1x1 PNG verified with vLLM
PNG_BYTES = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")

# Minimal valid 44-byte WAV audio file (silence)
WAV_BYTES = (
    b"RIFF,\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00"
    b"\x88X\x01\x00\x02\x00\x10\x00data\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
)

results = []

def record(name: str, passed: bool, detail: str = ""):
    results.append({"name": name, "passed": passed, "detail": detail})
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {name}: {detail}")

def run():
    client = httpx.Client(base_url=BASE_URL, timeout=60.0)

    # 1. Health
    res = client.get("/health")
    record("Health Probe", res.status_code == 200, f"HTTP {res.status_code}")

    # 2. Register
    reg_res = client.post("/api/v1/auth/register", json={"username": TEST_USER, "password": TEST_PASS})
    record("Auth Register", reg_res.status_code in (200, 201), f"HTTP {reg_res.status_code}")

    # 3. Login
    login_res = client.post("/api/v1/auth/login", data={"username": TEST_USER, "password": TEST_PASS})
    token = login_res.json().get("access_token") if login_res.status_code == 200 else None
    record("Auth Login", bool(token), f"HTTP {login_res.status_code}")
    auth_headers = {"Authorization": f"Bearer {token}"} if token else {}

    # 4. /auth/me
    me_res = client.get("/api/v1/auth/me", headers=auth_headers)
    me_data = me_res.json() if me_res.status_code == 200 else {}
    has_fields = "id" in me_data and "username" in me_data and "email" in me_data and "full_name" in me_data
    record("Auth Me Contract", me_res.status_code == 200 and has_fields, f"User: {me_data.get('username')}, full_name: {me_data.get('full_name')}")

    # 5. Normal Ingestion: Text
    text_res = client.post(
        "/api/v1/memories/ingest",
        json={"media_type": "text", "text": "Deploy verification note: all stability and ingestion fixes integrated.", "privacy": "ONLY_ME"},
        headers=auth_headers
    )
    raw_id1 = text_res.headers.get("X-Raw-Input-Id")
    phase1_id1 = text_res.headers.get("X-Phase1-Output-Id")
    record("Normal Text Ingestion", text_res.status_code == 200 and bool(raw_id1), f"Raw ID: {raw_id1}, Phase1 ID: {phase1_id1}")

    # 6. Normal Ingestion: Image (Multipart)
    img_files = {"file": ("test_verify.png", io.BytesIO(PNG_BYTES), "image/png")}
    img_data = {"media_type": "image", "privacy": "ONLY_ME", "allowed_users": "[]", "context": "Verification test image"}
    img_res = client.post("/api/v1/memories/ingest/image", files=img_files, data=img_data, headers=auth_headers)
    raw_id_img = img_res.headers.get("X-Raw-Input-Id")
    record("Normal Image Multipart Ingestion", img_res.status_code == 200 and bool(raw_id_img), f"Raw ID: {raw_id_img}")

    # 7. Normal Ingestion: Audio (Multipart)
    aud_files = {"file": ("test_verify.wav", io.BytesIO(WAV_BYTES), "audio/wav")}
    aud_data = {"media_type": "audio", "privacy": "ONLY_ME", "allowed_users": "[]", "context": "Verification test audio"}
    aud_res = client.post("/api/v1/memories/ingest/audio", files=aud_files, data=aud_data, headers=auth_headers)
    raw_id_aud = aud_res.headers.get("X-Raw-Input-Id")
    record("Normal Audio Multipart Ingestion", aud_res.status_code == 200 and bool(raw_id_aud), f"Raw ID: {raw_id_aud}")

    # Wait 1s for pipeline async settlement
    time.sleep(1.0)

    # 8. Normal Feed Retrieval
    feed_res = client.get("/api/v1/memories/feed?limit=10", headers=auth_headers)
    feed_items = feed_res.json().get("items", []) if feed_res.status_code == 200 else []
    record("Normal Feed Retrieval", feed_res.status_code == 200 and len(feed_items) >= 3, f"Total items: {len(feed_items)}")

    # 9. Semantic Search
    search_res = client.post(
        "/api/v1/memories/search",
        json={"query": "stability fixes", "top_k": 5, "generate_answer": False},
        headers=auth_headers
    )
    search_results = search_res.json().get("results", []) if search_res.status_code == 200 else []
    record("Semantic Search", search_res.status_code == 200, f"Found results: {len(search_results)}")

    # 10. Private Locker: Initial Status
    st_res = client.get("/api/v1/locker/status", headers=auth_headers)
    st_data = st_res.json() if st_res.status_code == 200 else {}
    record("Locker Status Initial", st_res.status_code == 200 and st_data.get("exists") is False, f"exists: {st_data.get('exists')}, status: {st_data.get('status')}")

    # 11. Private Locker: Create
    create_res = client.post("/api/v1/locker/create", json={"password": LOCKER_PASS}, headers=auth_headers)
    rec_key = create_res.json().get("recovery_key") if create_res.status_code == 200 else None
    record("Locker Create", create_res.status_code == 200 and bool(rec_key), f"Recovery Key generated")

    # 12. Private Locker: Unlock
    unlock_res = client.post("/api/v1/locker/unlock", json={"password": LOCKER_PASS}, headers=auth_headers)
    locker_token = unlock_res.json().get("locker_token") if unlock_res.status_code == 200 else None
    record("Locker Unlock", unlock_res.status_code == 200 and bool(locker_token), f"Locker Token: {bool(locker_token)}")
    locker_headers = {**auth_headers, "X-Locker-Token": locker_token} if locker_token else auth_headers

    # 13. Private Text Ingestion
    ptext_res = client.post(
        "/api/v1/memories/ingest",
        json={"media_type": "text", "text": "Secret financial credentials in private locker.", "privacy": "PRIVATE_LOCKER"},
        headers=locker_headers
    )
    raw_pid = ptext_res.headers.get("X-Raw-Input-Id")
    record("Private Locker Text Ingestion", ptext_res.status_code == 200 and bool(raw_pid), f"Private Raw ID: {raw_pid}")

    # 14. Private Image Ingestion
    pimg_files = {"file": ("private_doc.png", io.BytesIO(PNG_BYTES), "image/png")}
    pimg_data = {"media_type": "image", "privacy": "PRIVATE_LOCKER", "allowed_users": "[]", "context": "Private passport photo"}
    pimg_res = client.post("/api/v1/memories/ingest/image", files=pimg_files, data=pimg_data, headers=locker_headers)
    raw_pimg_id = pimg_res.headers.get("X-Raw-Input-Id")
    record("Private Locker Image Ingestion", pimg_res.status_code == 200 and bool(raw_pimg_id), f"Private Image Raw ID: {raw_pimg_id}")

    # 15. Private Audio Ingestion
    paud_files = {"file": ("private_rec.wav", io.BytesIO(WAV_BYTES), "audio/wav")}
    paud_data = {"media_type": "audio", "privacy": "PRIVATE_LOCKER", "allowed_users": "[]", "context": "Private voice note"}
    paud_res = client.post("/api/v1/memories/ingest/audio", files=paud_files, data=paud_data, headers=locker_headers)
    raw_paud_id = paud_res.headers.get("X-Raw-Input-Id")
    record("Private Locker Audio Ingestion", paud_res.status_code == 200 and bool(raw_paud_id), f"Private Audio Raw ID: {raw_paud_id}")

    # Wait 1s for pipeline async settlement
    time.sleep(1.0)

    # 16. Private Memories Listing
    pmem_res = client.get("/api/v1/locker/memories", headers=locker_headers)
    pmem_data = pmem_res.json() if pmem_res.status_code == 200 else {}
    pmem_items = pmem_data.get("items", []) if isinstance(pmem_data, dict) else (pmem_data if isinstance(pmem_data, list) else [])
    record("Private Locker Memories Retrieval", pmem_res.status_code == 200 and len(pmem_items) >= 3, f"Total private memories: {len(pmem_items)}")

    # 17. Feed Isolation: Locked feed vs Unlocked feed
    feed_locked = client.get("/api/v1/memories/feed?limit=20", headers=auth_headers).json().get("items", [])
    has_secret_in_locked = any("Secret financial" in (item.get("raw_payload") or "") for item in feed_locked)
    record("Locker Feed Isolation (Without Token)", not has_secret_in_locked, "Private memory hidden in standard locked feed")

    feed_unlocked = client.get("/api/v1/memories/feed?limit=20", headers=locker_headers).json().get("items", [])
    has_secret_in_unlocked = any("Secret financial" in (item.get("raw_payload") or "") for item in feed_unlocked)
    record("Locker Feed Integration (With Token)", has_secret_in_unlocked, "Private memory accessible when unlocked")

    # 18. Private Search
    psearch_res = client.post(
        "/api/v1/memories/search",
        json={"query": "financial credentials", "top_k": 5, "generate_answer": False},
        headers=locker_headers
    )
    record("Private Semantic Search (With Token)", psearch_res.status_code == 200, f"Status: {psearch_res.status_code}")

    # 19. Lock Locker
    lock_res = client.post("/api/v1/locker/lock", headers=locker_headers)
    record("Locker Lock Action", lock_res.status_code == 200, f"HTTP {lock_res.status_code}")

    # 20. Unauthorized Rejection After Lock
    re_res = client.get("/api/v1/locker/memories", headers=locker_headers)
    record("Revocation Enforcement", re_res.status_code in (401, 403), f"HTTP {re_res.status_code} (Properly Rejected)")

    # 21. Auth Logout
    logout_res = client.post("/api/v1/auth/logout", headers=auth_headers)
    record("Auth Logout", logout_res.status_code == 200, f"HTTP {logout_res.status_code}")

    print("\n" + "=" * 50)
    print("      END-TO-END VERIFICATION SUMMARY")
    print("=" * 50)
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    print(f"Total: {total}, Passed: {passed}, Failed: {total - passed}")
    if passed == total:
        print(">>> ALL LIVE TESTS PASSED 100% CLEAN! <<<")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    run()
