import httpx
import uuid
import time
import os
import sys

BASE_URL = "http://127.0.0.1:8000"
client = httpx.Client(timeout=30.0)

results = []

def record(test_id, test_name, expected, actual, status, evidence):
    results.append({
        "id": test_id,
        "test": test_name,
        "expected": expected,
        "actual": actual,
        "status": status,
        "evidence": evidence
    })
    print(f"[{status}] {test_id}: {test_name} -> {actual}")

def generate_user():
    return {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "Password123!",
        "full_name": "Test User"
    }

def register(user):
    resp = client.post(f"{BASE_URL}/api/v1/auth/register", json={
        "username": user["email"],
        "password": user["password"],
        "full_name": user["full_name"]
    })
    return resp

def login(email, password):
    resp = client.post(f"{BASE_URL}/api/v1/auth/login", data={"username": email, "password": password})
    return resp

def create_locker(jwt, password):
    resp = client.post(f"{BASE_URL}/api/v1/locker/create", json={"password": password}, headers={"Authorization": f"Bearer {jwt}"})
    return resp

def unlock_locker(jwt, password):
    resp = client.post(f"{BASE_URL}/api/v1/locker/unlock", json={"password": password}, headers={"Authorization": f"Bearer {jwt}"})
    return resp

def lock_locker(jwt, locker_token):
    resp = client.post(f"{BASE_URL}/api/v1/locker/lock", headers={"Authorization": f"Bearer {jwt}", "X-Locker-Token": locker_token})
    return resp

def main():
    print("Starting E2E Adversarial Tests...")
    
    # 1. ACCOUNT AUTHENTICATION TESTS
    # Valid signup
    user_a = generate_user()
    r1 = register(user_a)
    if r1.status_code == 200 or r1.status_code == 201:
        record("AUTH-1", "Valid Signup", "200/201", str(r1.status_code), "PASS", str(r1.json()))
    else:
        record("AUTH-1", "Valid Signup", "200/201", str(r1.status_code), "FAIL", r1.text)

    # Duplicate email
    r2 = register(user_a)
    if r2.status_code in [400, 422]:
        record("AUTH-2", "Duplicate Email", "400/422", str(r2.status_code), "PASS", r2.text)
    else:
        record("AUTH-2", "Duplicate Email", "400/422", str(r2.status_code), "FAIL", r2.text)
        
    # Malformed email
    r3 = register({"email": "not-an-email", "password": "abc", "full_name": "X"})
    if r3.status_code in [400, 422]:
        record("AUTH-3", "Malformed Email", "400/422", str(r3.status_code), "PASS", r3.text)
    else:
        record("AUTH-3", "Malformed Email", "400/422", str(r3.status_code), "FAIL", r3.text)

    # Login
    l1 = login(user_a["email"], user_a["password"])
    if l1.status_code == 200:
        jwt_a = l1.json()["access_token"]
        record("AUTH-4", "Valid Login", "200", str(l1.status_code), "PASS", "JWT returned")
    else:
        record("AUTH-4", "Valid Login", "200", str(l1.status_code), "FAIL", l1.text)
        return

    # Wrong password
    l2 = login(user_a["email"], "wrongpass")
    if l2.status_code in [401, 400]:
        record("AUTH-5", "Wrong Password", "401", str(l2.status_code), "PASS", l2.text)
    else:
        record("AUTH-5", "Wrong Password", "401", str(l2.status_code), "FAIL", l2.text)

    # 2. LOCKER CREATION
    c1 = create_locker(jwt_a, "LockerPass123!")
    if c1.status_code in [200, 201]:
        record("LOCK-1", "Create Locker", "200", str(c1.status_code), "PASS", "Created")
    else:
        record("LOCK-1", "Create Locker", "200", str(c1.status_code), "FAIL", c1.text)
        
    c2 = create_locker(jwt_a, "AnotherPass!")
    if c2.status_code in [400, 409]:
        record("LOCK-2", "Duplicate Locker", "400/409", str(c2.status_code), "PASS", c2.text)
    else:
        record("LOCK-2", "Duplicate Locker", "400/409", str(c2.status_code), "FAIL", c2.text)

    # 3. LOCKER UNLOCK
    u1 = unlock_locker(jwt_a, "LockerPass123!")
    if u1.status_code == 200:
        locker_token_a = u1.json()["locker_token"]
        record("UNLK-1", "Valid Unlock", "200", str(u1.status_code), "PASS", "Token returned")
    else:
        record("UNLK-1", "Valid Unlock", "200", str(u1.status_code), "FAIL", u1.text)
        return

    u2 = unlock_locker(jwt_a, "wrongpass")
    if u2.status_code in [401, 403]:
        record("UNLK-2", "Wrong Unlock Password", "401/403", str(u2.status_code), "PASS", u2.text)
    else:
        record("UNLK-2", "Wrong Unlock Password", "401/403", str(u2.status_code), "FAIL", u2.text)

    # 7. PRIVATE TEXT INGESTION
    t1 = client.post(f"{BASE_URL}/api/v1/memories/ingest", json={
        "text": "My private locker contains sapphire-orchid-92817.",
        "media_type": "text",
        "privacy": "PRIVATE_LOCKER"
    }, headers={"Authorization": f"Bearer {jwt_a}", "X-Locker-Token": locker_token_a})
    
    if t1.status_code in [200, 201]:
        record("INGEST-1", "Private Ingest Unlocked", "200/201", str(t1.status_code), "PASS", t1.text)
    else:
        record("INGEST-1", "Private Ingest Unlocked", "200/201", str(t1.status_code), "FAIL", t1.text)

    # Locked ingest attempt
    t2 = client.post(f"{BASE_URL}/api/v1/memories/ingest", json={
        "text": "Another private one",
        "media_type": "text",
        "privacy": "PRIVATE_LOCKER"
    }, headers={"Authorization": f"Bearer {jwt_a}"})
    
    if t2.status_code in [401, 403]:
        record("INGEST-2", "Private Ingest Locked", "401/403", str(t2.status_code), "PASS", t2.text)
    else:
        record("INGEST-2", "Private Ingest Locked", "401/403", str(t2.status_code), "FAIL", t2.text)

    # 10. VECTOR SEARCH / SEMANTIC ISOLATION
    s1 = client.post(f"{BASE_URL}/api/v1/memories/search", json={"query": "sapphire-orchid"}, headers={"Authorization": f"Bearer {jwt_a}"})
    if s1.status_code == 200:
        res = s1.json().get("results", [])
        found = any("sapphire-orchid" in r.get("memory", {}).get("content", {}).get("clean_text", "") for r in res)
        if not found:
            record("SEARCH-1", "Search Locked (No Leak)", "False", str(found), "PASS", "Private item hidden")
        else:
            record("SEARCH-1", "Search Locked (No Leak)", "False", str(found), "FAIL", "Item leaked!")
    else:
        record("SEARCH-1", "Search Locked", "200", str(s1.status_code), "FAIL", s1.text)

    s2 = client.post(f"{BASE_URL}/api/v1/memories/search", json={"query": "sapphire-orchid"}, headers={"Authorization": f"Bearer {jwt_a}", "X-Locker-Token": locker_token_a})
    if s2.status_code == 200:
        res = s2.json().get("results", [])
        found = any("sapphire-orchid" in r.get("memory", {}).get("content", {}).get("clean_text", "") for r in res)
        if found:
            record("SEARCH-2", "Search Unlocked", "True", str(found), "PASS", "Private item found")
        else:
            record("SEARCH-2", "Search Unlocked", "True", str(found), "FAIL", "Item not found")
    else:
        record("SEARCH-2", "Search Unlocked", "200", str(s2.status_code), "FAIL", s2.text)

    # USER B tests
    user_b = generate_user()
    register(user_b)
    l_b = login(user_b["email"], user_b["password"])
    jwt_b = l_b.json()["access_token"]
    
    s3 = client.post(f"{BASE_URL}/api/v1/memories/search", json={"query": "sapphire-orchid"}, headers={"Authorization": f"Bearer {jwt_b}"})
    if s3.status_code == 200:
        found = any("sapphire-orchid" in r.get("memory", {}).get("content", {}).get("clean_text", "") for r in s3.json().get("results", []))
        if not found:
            record("SEARCH-3", "User B Search A Private", "False", str(found), "PASS", "Hidden")
        else:
            record("SEARCH-3", "User B Search A Private", "False", str(found), "FAIL", "Leaked to B")
            
    # Token Security
    s4 = client.post(f"{BASE_URL}/api/v1/memories/search", json={"query": "sapphire-orchid"}, headers={"Authorization": f"Bearer {jwt_b}", "X-Locker-Token": locker_token_a})
    if s4.status_code == 200:
        found = any("sapphire-orchid" in r.get("memory", {}).get("content", {}).get("clean_text", "") for r in s4.json().get("results", []))
        if not found:
            record("TOKEN-1", "User B using User A Locker Token", "False", str(found), "PASS", "Private item hidden")
        else:
            record("TOKEN-1", "User B using User A Locker Token", "False", str(found), "FAIL", "Item leaked!")
    else:
        record("TOKEN-1", "User B using User A Locker Token", "200", str(s4.status_code), "FAIL", s4.text)
        
    # Manual Lock
    lk1 = lock_locker(jwt_a, locker_token_a)
    if lk1.status_code == 200:
        record("MANUAL-1", "Manual Lock", "200", str(lk1.status_code), "PASS", lk1.text)
        
        # Verify unlocked search fails (or hides private items)
        s5 = client.post(f"{BASE_URL}/api/v1/memories/search", json={"query": "sapphire-orchid"}, headers={"Authorization": f"Bearer {jwt_a}", "X-Locker-Token": locker_token_a})
        if s5.status_code == 200:
            found = any("sapphire-orchid" in r.get("memory", {}).get("content", {}).get("clean_text", "") for r in s5.json().get("results", []))
            if not found:
                record("MANUAL-2", "Search after manual lock", "False", str(found), "PASS", "Private item hidden")
            else:
                record("MANUAL-2", "Search after manual lock", "False", str(found), "FAIL", "Item leaked!")
        else:
            record("MANUAL-2", "Search after manual lock", "200", str(s5.status_code), "FAIL", s5.text)
    else:
        record("MANUAL-1", "Manual Lock", "200", str(lk1.status_code), "FAIL", lk1.text)

    # Save report
    import json
    with open("e2e_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Done")

if __name__ == "__main__":
    main()
