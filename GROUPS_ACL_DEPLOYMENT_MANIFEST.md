# MINDMESH GROUPS, RBAC & ACL DEPLOYMENT MANIFEST

## 1. Executive Summary

This manifest documents all modified and newly created files for the **MindMesh Groups, 5-Role RBAC, Resource-Level ACL, Feed, Comments, and AI Pipeline Integration**.

- **Target Staging Destination (Future Deployment Only)**:
  `/home/coeai/mindmesh_copy/mindmesh`
- **Protected Production Target (Never Modified)**:
  `/home/coeai/mindmesh`
- **Local Windows Source**:
  `F:\MindMesh-mindmesh-core\MindMesh-mindmesh-core`
- **Local Backup Snapshot**:
  `F:\MindMesh-mindmesh-core_backup_groups_task_20261022_024424\MindMesh-mindmesh-core`
- **Release Bundle**:
  `MindMesh_Groups_Release.zip`
- **Release Bundle SHA-256**:
  `87138ec6c1ebea2cd59a412e689903a4f7f2ce9da0e6200f7fb0bb4007a5be43`

---

## 2. File Inventory & SHA-256 Checksums

### A. New Backend & Migration Files (14 files)

| Relative Path | SHA-256 Checksum | Category | Description |
|---|---|---|---|
| `backend/app/api/routes/groups.py` | `d6f733c3758b96b7295650d43bf5b31306cf05a5e9cef62e982df2e1fe1a45ce` | API Route | Group CRUD, member management, invitation tokens, ownership transfer |
| `backend/app/api/routes/comments.py` | `3ea6bfca7bf8eef4c2f5683bc9001891c5e353765d8e3471671ea2ea81f390d2` | API Route | Collaborative comments, knowledge promotion, moderation |
| `backend/app/database/migrations/004_groups_and_acl.sql` | `6735fa73456d7b06040e218f2fcf8d6eec91ba943f6994bed9ee144c3a31727c` | SQL Migration | Forward migration for groups, memberships, invitations, ACL, and comments |
| `backend/app/database/migrations/004_rollback_groups_and_acl.sql` | `aadf0e7131f7db9581cf0f197d4afe437a008fc3b4fddfd081a0ee5f1f82afbd` | Rollback SQL | Safe rollback script (isolated from forward runner) |
| `backend/app/database/models/groups.py` | `cf87bc80e52683ea96b0328ed24f25b5c7cbded83c4eb05c5906952706f06331` | SQLAlchemy Model | GroupModel, GroupMemberModel, GroupInvitationModel, MemoryGroupAccessModel, etc. |
| `backend/app/database/models/comments.py` | `c3a388dcf2251933230c23c2cb8dfbf24c70efdace1b30f292626665346f2516` | SQLAlchemy Model | CommentModel schema and relationships |
| `backend/app/schemas/group.py` | `f6c0564c43b66f29f333a6d7ee878d1549533d3f29d0c3c00975513b8ac3b5c9` | Pydantic Schema | Pydantic v2 schemas for groups, members, invitations, shares |
| `backend/app/schemas/comment.py` | `16405f67f25e0ba924db5d14bf8774201ffd963bd9ed2d036e74834ac280ac45` | Pydantic Schema | Pydantic v2 schemas for comments request and response |
| `backend/app/services/group_service.py` | `e2781b8ed06f2e6b0617a5251754747c5189b5a4c1763cfdedbcfa20798a0df6` | Service | Group lifecycle, invitations, 5-role RBAC checks, user search |
| `backend/app/services/share_service.py` | `d212bd85e5857cf77c443ab1a62dbe821a17fae32c350c199c694cb14c2cf308` | Service | Resource-level sharing, multi-group, direct user ACL, Private Locker guard |
| `backend/app/services/comment_service.py` | `c4473f5315bef5c7006eceeb69173529265d73c79a86ec439892f3289f979efa` | Service | Commenting, substantive knowledge eligibility (Phase 1 sync) |
| `backend/tests/test_migration_runner_security.py` | `1de01d1f06cbbaf50ae6b47ac7715c666cbe239a17de19bc4d9838843482a35c` | Automated Test | Verifies runner excludes rollback files and preserves ordering |
| `backend/tests/test_groups_lifecycle_e2e.py` | `f96f48efe009ef915c34a3c3bb147d966e3a4b2588b1254de3a63df1dc691614` | Automated Test | Scenarios A-H E2E RBAC, ACL, Search, AI answer, and Private Locker firewall |
| `backend/tests/test_groups_api_routes.py` | `2fa82003cf9a28653cca6828a5d06cb7cf3766a5bd51dc7d886a5e4822c6034a` | Automated Test | Full HTTP API route flow via AsyncClient |

### B. Modified Shared Backend Files (10 files)

| Relative Path | SHA-256 Checksum | Category | Description |
|---|---|---|---|
| `backend/app/core/enums.py` | `746d57c4c2b0927900edc243dfc5addb0bde5b70ba703827672a4ab7cb8bb61d` | Core Enums | Harmonized Privacy (`SHARED`, `PUBLIC`, legacy preservation), added `GroupRole`, `InvitationStatus` |
| `backend/app/main.py` | `1dd6b1477e33a94832161ef46a0c59b1016d04914f876b6c2c3eb51fce5a1f2a` | Main Entry | Mounted `groups_router` and `comments_router` |
| `backend/app/database/models/__init__.py` | `d4fb83a45b852b1934c5ccb38111f30a1d89c38017afc8b7a7b3e459db610da7` | Model Registry | Exported group, member, invitation, access, and comment models |
| `backend/app/database/migrations/runner.py` | `6e2bf6f99c5f8d815cb4ecf859d96f1d11d3af7ce79b9392bbe71e18e4848e2d` | Migration Runner | Hardened forward runner: ignores rollback files, sorts, tracks `schema_migrations` |
| `backend/app/database/repositories/phase2_embedding_repo.py` | `3032382be7e090e444ab7a95cc0a198dcbc9f8ab4cb9b33bf39339903963d0d4` | Repository | Added `find_by_ids` for candidate filtering |
| `backend/app/schemas/search_schemas.py` | `394991f247a75653530a36c00aeaac86264255630cfc4bd974eed01ea2e0f287` | Schema | Added `group_id: Optional[Any]` parameter |
| `backend/app/services/authz_service.py` | `44fd17e14020ec40fe354a63b62ea33b2735eba8b7c4da013e28219c47c67554` | Authorization | 5-role RBAC + resource ACL evaluation, query boundary filtering, Private Locker guard |
| `backend/app/services/memory_search_service.py` | `1933e294c5327e9ba38bebdf041f3fc29611e18c06a297b17e008bb26da5369c` | Search & AI | Query-boundary ACL candidate restriction, removal of `GROUP`/`PUBLIC` bypass |
| `backend/app/api/routes/memories.py` | `13e1b8943485f1a1ff8f99b7108829a175b62f3b50a0ec40debcc7389e629ce0` | API Route | Group validation on ingest, feed membership check, share/revoke routes, search group filter |
| `backend/app/api/routes/media.py` | `a90623a3118544c20f784d142ce06d0b30ef284893e1434c44243a3d537f1947` | Media Route | Group membership verification fallback for shared media streaming |

### C. Frontend Files (9 files)

| Relative Path | SHA-256 Checksum | Category | Description |
|---|---|---|---|
| `mindmesh-mobile/src/types/index.ts` | `538994a97561516226d61f34c6a84ac9d201d90ffd0532b7a8f9f600479efcb6` | TypeScript Types | Added `groups` and `group_detail` screens, `Group`, `GroupMember`, `GroupInvitation`, `CommentItem` |
| `mindmesh-mobile/src/services/apiClient.ts` | `c79a9bef4128fe7e10577f6aeac73ad92e2f6ee5d2c1b9431129ee9a7cbec3f3` | API Client | Added all Groups, Members, Invitations, Shares, and Comments API calls |
| `mindmesh-mobile/src/components/FloatingBottomDock.tsx` | `0b8539f8eee7cb64343f634855f9b8622442140157144c14b6478b2578fb048c` | UI Component | Added Groups navigation tab with cream/forest green theme |
| `mindmesh-mobile/src/screens/GroupsScreen.tsx` | `1ae306d7aef23b174be4fd4f32434d2f7a671657cf0fca676c0710ac51cb9aa0` | Screen (New) | Groups listing, create modal, invitation token modal |
| `mindmesh-mobile/src/screens/GroupDetailScreen.tsx` | `9759071cc57272e0aaf1932436865fcfb51e5db1e5b054c6ca45c59c65b3fe5c` | Screen (New) | Group feed, member roles, invite creation, transfer ownership, settings |
| `mindmesh-mobile/App.tsx` | `687a1c5854d4708639568991010112ba40c5b4e226ced896d1a4230db7f482ee` | Navigation Root | Mounted GroupsScreen and GroupDetailScreen |
| `mindmesh-mobile/src/screens/ComposerScreen.tsx` | `80d942be78d410baa79f023a68354c6940de211a1ee13cdfbc5f49034b01192f` | Screen | Group destination selection and `group_id` transmission |
| `mindmesh-mobile/src/screens/MemoryDetailScreen.tsx` | `f4965058d9751ee70c8f631f691eee1607dc21910844e2fdf712fccf1afc5c44` | Screen | Share to Group modal, collaborative comments section |
| `mindmesh-mobile/src/screens/VaultScreen.tsx` | `3690a77d0ce2cc18c02e62c748a08af47bc1fd931dccf00b62f4c64365ba97e2` | Screen | Group semantic filter chips for vector search and AI answer generation |

---

## 3. Database Migration Sequence

1. **Preflight Verification**:
   Verify migration history table `schema_migrations` exists:
   ```sql
   CREATE TABLE IF NOT EXISTS schema_migrations (
       filename VARCHAR(255) PRIMARY KEY,
       applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
   );
   ```
2. **Execute Migration**:
   Apply `backend/app/database/migrations/004_groups_and_acl.sql`.
   The runner automatically validates that `*rollback*.sql` files are excluded and records `004_groups_and_acl.sql` in `schema_migrations`.
3. **Verify Created Tables**:
   - `groups`
   - `group_members`
   - `group_invitations`
   - `memory_group_access`
   - `memory_user_access`
   - `group_feed_references`
   - `group_activities`
   - `memory_comments`

---

## 4. Safe Deployment Procedure (Debian Staging)

> **STRICT SAFETY CONSTRAINT**: Do not deploy during this local task. When ready for deployment to `/home/coeai/mindmesh_copy/mindmesh`:

1. **Backup Staging Directory**:
   ```bash
   cp -r /home/coeai/mindmesh_copy/mindmesh /home/coeai/mindmesh_copy/mindmesh_backup_$(date +%Y%m%d_%H%M%S)
   ```
2. **Transfer `MindMesh_Groups_Release.zip`**:
   Transfer `MindMesh_Groups_Release.zip` to `/home/coeai/mindmesh_copy/` and extract with overwrite into `/home/coeai/mindmesh_copy/mindmesh`.
3. **Run Migration**:
   ```bash
   cd /home/coeai/mindmesh_copy/mindmesh
   python -m app.database.migrations.runner
   ```
4. **Run Verification Tests**:
   ```bash
   python -m pytest backend/tests/test_migration_runner_security.py backend/tests/test_groups_lifecycle_e2e.py backend/tests/test_groups_api_routes.py
   ```
5. **Restart Staging Service**:
   Identify the staging service specifically bound to `mindmesh_copy` (e.g., `systemctl restart mindmesh-copy` or staging daemon). Do NOT restart the production service.

---

## 5. Rollback Plan

If staging verification fails:
1. Revert files from the timestamped backup:
   ```bash
   cp -r /home/coeai/mindmesh_copy/mindmesh_backup_<timestamp>/* /home/coeai/mindmesh_copy/mindmesh/
   ```
2. If database rollback is explicitly required:
   Execute `004_rollback_groups_and_acl.sql` manually via psql.
3. Restart staging service.
