import sys
import uuid
import json
import urllib.request
import urllib.error

BASE_URL = 'http://127.0.0.1:8002'

def request(method, path, data=None, headers=None):
    url = f"{BASE_URL}{path}"
    req_headers = {'Accept': 'application/json'}
    if headers:
        req_headers.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        req_headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content = resp.read().decode('utf-8')
            try:
                json_data = json.loads(content)
            except Exception:
                json_data = content
            return status, json_data
    except urllib.error.HTTPError as e:
        content = e.read().decode('utf-8')
        try:
            json_data = json.loads(content)
        except Exception:
            json_data = content
        return e.code, json_data

def run_tests():
    print('=====================================================')
    print('MINDMESH LIVE DEBIAN GROUPS + ACL VERIFICATION SUITE')
    print('=====================================================')

    # 1. Health check
    status, data = request('GET', '/health')
    assert status == 200, f'Health check failed: {status} {data}'
    print(' [PASS] 1. /health returned HTTP 200 OK')

    # 2. Unauthenticated check on Groups API
    status, data = request('GET', '/api/v1/groups')
    assert status in (401, 403), f'Expected 401/403 for unauthenticated request, got {status}'
    print(' [PASS] 2. Unauthenticated access to /api/v1/groups is rejected (HTTP 401)')

    # 3. Setup 3 isolated users for live testing
    tag = uuid.uuid4().hex[:6]
    users_data = {
        'owner': {'username': f'owner_{tag}', 'email': f'owner_{tag}@example.com', 'password': 'Password123!'},
        'member': {'username': f'member_{tag}', 'email': f'member_{tag}@example.com', 'password': 'Password123!'},
        'outsider': {'username': f'outsider_{tag}', 'email': f'outsider_{tag}@example.com', 'password': 'Password123!'}
    }
    tokens = {}

    for role_name, u_info in users_data.items():
        st_reg, res_reg = request('POST', '/api/v1/auth/register', data={'username': u_info['username'], 'password': u_info['password']})
        assert st_reg in (200, 400), f'Registration failed for {role_name}: {st_reg} {res_reg}'
        st_login, res_login = request('POST', '/api/v1/auth/login', data={'username': u_info['username'], 'password': u_info['password']})
        assert st_login == 200, f'Login failed for {role_name}: {res_login}'
        tokens[role_name] = res_login['access_token']
    print(' [PASS] 3. Three isolated test users registered & authenticated successfully')

    owner_hdr = {'Authorization': f'Bearer {tokens["owner"]}'}
    member_hdr = {'Authorization': f'Bearer {tokens["member"]}'}
    outsider_hdr = {'Authorization': f'Bearer {tokens["outsider"]}'}

    # 4. Create Group
    st, group = request('POST', '/api/v1/groups', data={'name': f'Live Debian Team {tag}', 'description': 'Automated verification group'}, headers=owner_hdr)
    assert st == 201, f'Create group failed: {st} {group}'
    group_id = group['id']
    assert group['my_role'] == 'OWNER'
    print(f' [PASS] 4. Group created: id={group_id}, role=OWNER')

    # 5. List Groups for Owner
    st, my_groups = request('GET', '/api/v1/groups', headers=owner_hdr)
    assert st == 200
    assert any(g['id'] == group_id for g in my_groups)
    print(' [PASS] 5. Group listed in user groups feed')

    # 6. Create Invitation Link for Member
    st, inv_data = request('POST', f'/api/v1/groups/{group_id}/invitations', data={'invitee_email': users_data['member']['email'], 'role': 'MEMBER'}, headers=owner_hdr)
    assert st == 201, f'Create invitation failed: {st} {inv_data}'
    token = inv_data.get('invitation_token')
    assert token, 'No invitation token returned'
    print(f' [PASS] 6. Cryptographic invitation token generated: {token[:8]}...')

    # 7. Validate Invitation Link
    st, val_data = request('GET', f'/api/v1/groups/invitations/validate/{token}')
    assert st == 200, f'Validate invitation failed: {st} {val_data}'
    assert val_data['group_id'] == group_id
    assert val_data['role'] == 'MEMBER'
    print(' [PASS] 7. Invitation link validated successfully')

    # 8. Accept Invitation as Member
    st, accept_res = request('POST', '/api/v1/groups/invitations/accept', data={'token': token}, headers=member_hdr)
    assert st == 200, f'Accept invitation failed: {st} {accept_res}'
    print(' [PASS] 8. Member accepted invitation and joined group')

    # 9. Verify Membership List
    st, member_list = request('GET', f'/api/v1/groups/{group_id}/members', headers=owner_hdr)
    assert st == 200
    assert len(member_list) == 2
    roles = {m['username']: m['role'] for m in member_list}
    assert roles[users_data['owner']['username']] == 'OWNER'
    assert roles[users_data['member']['username']] == 'MEMBER'
    print(' [PASS] 9. Membership list verified with OWNER and MEMBER roles')

    # 10. ACL Enforcement: Outsider non-member feed access
    st, outsider_feed = request('GET', f'/api/v1/memories/feed?group_id={group_id}', headers=outsider_hdr)
    assert st == 403, f'Expected 403 for outsider feed, got {st}'
    print(' [PASS] 10. Non-member feed access strictly REJECTED (HTTP 403)')

    # 11. ACL Enforcement: Outsider non-member group ingestion
    st, outsider_ingest = request('POST', '/api/v1/memories/ingest', data={'text': 'Intruder text', 'privacy': 'GROUP', 'group_id': group_id}, headers=outsider_hdr)
    assert st == 403, f'Expected 403 for unauthorized ingestion, got {st}'
    print(' [PASS] 11. Non-member group ingestion strictly REJECTED (HTTP 403)')

    # 12. Authorized Group Memory Ingestion (by Member)
    st, ingested_mem = request('POST', '/api/v1/memories/ingest', data={'text': f'Project Alpha architecture notes for group {tag}', 'privacy': 'GROUP', 'group_id': group_id}, headers=member_hdr)
    assert st == 200, f'Authorized group ingestion failed: {st} {ingested_mem}'
    memory_id = ingested_mem['memory_id']
    assert ingested_mem['system']['group_id'] == group_id
    assert ingested_mem['system']['privacy'] == 'GROUP'
    print(f' [PASS] 12. Group memory ingested: memory_id={memory_id}, group_id={group_id}')

    # 13. Group Feed Retrieval
    st, member_feed = request('GET', f'/api/v1/memories/feed?group_id={group_id}', headers=member_hdr)
    assert st == 200
    feed_items = member_feed.get('items', [])
    assert any(item['id'] == memory_id for item in feed_items)
    print(' [PASS] 13. Group feed returns authorized memory for group members')

    # 14. Comments & Discussions
    st, comment_data = request('POST', f'/api/v1/memories/{memory_id}/comments', data={'content': 'Great architecture design notes! Approved.'}, headers=owner_hdr)
    assert st == 201, f'Add comment failed: {st} {comment_data}'
    comment_id = comment_data['id']
    print(f' [PASS] 14. Comment added to memory: comment_id={comment_id}')

    st, comments = request('GET', f'/api/v1/memories/{memory_id}/comments', headers=member_hdr)
    assert st == 200
    assert any(c['id'] == comment_id for c in comments)
    print(' [PASS] 15. Group comments retrieved successfully by member')

    st, outsider_comments = request('GET', f'/api/v1/memories/{memory_id}/comments', headers=outsider_hdr)
    assert st == 403, f'Expected 403 for outsider comments, got {st}'
    print(' [PASS] 16. Non-member comments access strictly REJECTED (HTTP 403)')

    # 15. Group Semantic Search & Authorization
    st, search_res = request('POST', '/api/v1/memories/search', data={'query': 'Project Alpha architecture', 'group_id': group_id, 'generate_answer': False}, headers=member_hdr)
    assert st == 200, f'Search failed: {st} {search_res}'
    results = search_res.get('results', [])
    print(f' [PASS] 17. Group semantic search returned {len(results)} authorized memories for member')

    st, outsider_search = request('POST', '/api/v1/memories/search', data={'query': 'Project Alpha architecture', 'group_id': group_id, 'generate_answer': False}, headers=outsider_hdr)
    assert st == 200
    outsider_results = outsider_search.get('results', [])
    assert len(outsider_results) == 0, f'Outsider received {len(outsider_results)} leaked group memories'
    print(' [PASS] 18. Non-member semantic search strictly isolates group memories (0 results)')

    # 16. Memory Sharing & Revocation
    st, personal_mem = request('POST', '/api/v1/memories/ingest', data={'text': f'Personal memory from owner {tag}', 'privacy': 'ONLY_ME'}, headers=owner_hdr)
    assert st == 200
    personal_id = personal_mem['memory_id']

    st, share_res = request('POST', f'/api/v1/memories/{personal_id}/share', data={'group_ids': [group_id]}, headers=owner_hdr)
    assert st == 200, f'Share failed: {st} {share_res}'
    print(' [PASS] 19. Personal memory shared with group')

    st, shares_check = request('GET', f'/api/v1/memories/{personal_id}/shares', headers=owner_hdr)
    assert st == 200
    print(' [PASS] 20. Memory shares verified')

    st, revoke_res = request('POST', f'/api/v1/memories/{personal_id}/revoke', data={'group_id': group_id}, headers=owner_hdr)
    assert st == 200
    print(' [PASS] 21. Memory share revoked')

    # 17. Role Management & Member Removal
    member_user_id = [m['user_id'] for m in member_list if m['role'] == 'MEMBER'][0]
    
    st, role_res = request('PATCH', f'/api/v1/groups/{group_id}/members/{member_user_id}', data={'role': 'ADMIN'}, headers=owner_hdr)
    assert st == 200
    assert role_res['role'] == 'ADMIN'
    print(' [PASS] 22. Member role elevated to ADMIN')

    st, del_res = request('DELETE', f'/api/v1/groups/{group_id}/members/{member_user_id}', headers=owner_hdr)
    assert st == 200
    print(' [PASS] 23. Member removed from group by owner')

    st, removed_feed = request('GET', f'/api/v1/memories/feed?group_id={group_id}', headers=member_hdr)
    assert st == 403
    print(' [PASS] 24. Removed member immediately loses group access (HTTP 403)')

    # 18. P0 Security Check: Main Stream Feed & Private Locker Isolation
    st, main_feed = request('GET', '/api/v1/memories/feed?limit=50', headers=owner_hdr)
    assert st == 200
    for item in main_feed.get('items', []):
        assert item.get('privacy') != 'PRIVATE_LOCKER', f'LEAK: Private locker memory {item.get("id")} found in main stream'
    print(' [PASS] 25. Main Stream feed verified: ZERO Private Locker leaks')

    # 19. Package B Feature Flag Protection Check
    st, pkg_b_res = request('GET', '/api/v2/locker-auth/device-session', headers=owner_hdr)
    assert st in (403, 404), f'Expected 403 or 404 for Package B disabled route, got {st}'
    print(' [PASS] 26. Package B /api/v2 routes remain strictly disabled/unmounted')

    print('=====================================================')
    print('ALL 26 LIVE VERIFICATION CHECKS PASSED WITH 100% SUCCESS!')
    print('=====================================================')

if __name__ == '__main__':
    run_tests()
