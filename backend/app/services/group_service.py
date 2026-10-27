import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GroupRole, InvitationStatus
from app.database.models.groups import (
    GroupActivityModel,
    GroupInvitationModel,
    GroupMemberModel,
    GroupModel,
)
from app.database.models.user import UserModel
from app.schemas.group import (
    GroupDetailResponse,
    GroupInvitationResponse,
    GroupMemberResponse,
    GroupResponse,
)


class GroupService:
    @staticmethod
    async def get_user_role(
        session: AsyncSession, group_id: uuid.UUID, user_id: str
    ) -> Optional[str]:
        """Fetch the user's role in a given group, or None if not an active member."""
        stmt = select(GroupMemberModel.role).where(
            and_(GroupMemberModel.group_id == group_id, GroupMemberModel.user_id == user_id)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def verify_membership(
        session: AsyncSession,
        group_id: uuid.UUID,
        user_id: str,
        required_roles: Optional[List[str]] = None,
    ) -> str:
        """Verify that user is a member of the group and meets optional role requirements.
        
        Raises HTTPException 404 if group doesn't exist.
        Raises HTTPException 403 if user is not a member or lacks the required role.
        """
        # 1. Check group existence and archive status
        group_stmt = select(GroupModel).where(GroupModel.id == group_id)
        group_res = await session.execute(group_stmt)
        group = group_res.scalar_one_or_none()
        if not group or group.is_archived:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group {group_id} not found or has been archived.",
            )

        # 2. Check membership
        role = await GroupService.get_user_role(session, group_id, user_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this group.",
            )

        # 3. Check role requirement if specified
        if required_roles and role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires one of the following roles: {required_roles}. Your role: {role}.",
            )

        return role

    @staticmethod
    async def create_group(
        session: AsyncSession,
        name: str,
        description: Optional[str],
        avatar_url: Optional[str],
        creator_id: str,
    ) -> GroupModel:
        """Atomically create a new group and assign the creator as OWNER."""
        new_group = GroupModel(
            name=name.strip(),
            description=description.strip() if description else None,
            avatar_url=avatar_url.strip() if avatar_url else None,
            created_by=creator_id,
        )
        session.add(new_group)
        await session.flush()

        # Add creator as OWNER
        owner_member = GroupMemberModel(
            group_id=new_group.id,
            user_id=creator_id,
            role=GroupRole.OWNER.value,
        )
        session.add(owner_member)

        # Log activity
        activity = GroupActivityModel(
            group_id=new_group.id,
            actor_id=creator_id,
            activity_type="GROUP_CREATED",
            details=f"Group '{name}' created by user {creator_id}.",
        )
        session.add(activity)

        await session.commit()
        await session.refresh(new_group)
        return new_group

    @staticmethod
    async def list_user_groups(
        session: AsyncSession, user_id: str
    ) -> List[dict]:
        """List all non-archived groups that the user is an active member of."""
        stmt = (
            select(
                GroupModel,
                GroupMemberModel.role,
                func.count(GroupMemberModel.user_id).over(partition_by=GroupModel.id).label("m_count"),
            )
            .join(GroupMemberModel, GroupMemberModel.group_id == GroupModel.id)
            .where(
                and_(
                    GroupMemberModel.user_id == user_id,
                    GroupModel.is_archived.is_(False),
                )
            )
            .order_by(GroupModel.created_at.desc())
        )
        res = await session.execute(stmt)
        rows = res.all()

        results = []
        for group, role, _ in rows:
            # Query actual total member count for this group
            cnt_stmt = select(func.count(GroupMemberModel.user_id)).where(GroupMemberModel.group_id == group.id)
            total_members = (await session.execute(cnt_stmt)).scalar() or 0
            results.append(
                {
                    "id": group.id,
                    "name": group.name,
                    "description": group.description,
                    "avatar_url": group.avatar_url,
                    "created_by": group.created_by,
                    "is_archived": group.is_archived,
                    "created_at": group.created_at,
                    "updated_at": group.updated_at,
                    "member_count": total_members,
                    "my_role": role,
                }
            )
        return results

    @staticmethod
    async def get_group_details(
        session: AsyncSession, group_id: uuid.UUID, user_id: str
    ) -> GroupDetailResponse:
        """Get group details along with member list and current user's permissions."""
        role = await GroupService.verify_membership(session, group_id, user_id)

        group_stmt = select(GroupModel).where(GroupModel.id == group_id)
        group = (await session.execute(group_stmt)).scalar_one()

        # Fetch members with usernames
        members_stmt = (
            select(GroupMemberModel, UserModel.username)
            .outerjoin(UserModel, UserModel.id == GroupMemberModel.user_id)
            .where(GroupMemberModel.group_id == group_id)
            .order_by(GroupMemberModel.joined_at.asc())
        )
        members_res = await session.execute(members_stmt)
        member_items = []
        for m, uname in members_res.all():
            member_items.append(
                GroupMemberResponse(
                    group_id=m.group_id,
                    user_id=m.user_id,
                    username=uname or m.user_id,
                    role=m.role,
                    joined_at=m.joined_at,
                )
            )

        can_manage = role in (GroupRole.OWNER.value, GroupRole.ADMIN.value)

        return GroupDetailResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            avatar_url=group.avatar_url,
            created_by=group.created_by,
            is_archived=group.is_archived,
            created_at=group.created_at,
            updated_at=group.updated_at,
            member_count=len(member_items),
            my_role=role,
            members=member_items,
            can_manage=can_manage,
        )

    @staticmethod
    async def update_group(
        session: AsyncSession,
        group_id: uuid.UUID,
        user_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> GroupModel:
        """Update group metadata. Requires OWNER or ADMIN role."""
        await GroupService.verify_membership(
            session, group_id, user_id, required_roles=[GroupRole.OWNER.value, GroupRole.ADMIN.value]
        )

        group_stmt = select(GroupModel).where(GroupModel.id == group_id)
        group = (await session.execute(group_stmt)).scalar_one()

        if name is not None:
            group.name = name.strip()
        if description is not None:
            group.description = description.strip() if description else None
        if avatar_url is not None:
            group.avatar_url = avatar_url.strip() if avatar_url else None
        group.updated_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(group)
        return group

    @staticmethod
    async def delete_group(
        session: AsyncSession, group_id: uuid.UUID, user_id: str
    ) -> None:
        """Delete / archive group. Strictly requires OWNER role."""
        role = await GroupService.verify_membership(session, group_id, user_id)
        if role != GroupRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the group OWNER can delete the group.",
            )

        group_stmt = select(GroupModel).where(GroupModel.id == group_id)
        group = (await session.execute(group_stmt)).scalar_one()
        group.is_archived = True
        group.updated_at = datetime.now(timezone.utc)

        # Log activity
        activity = GroupActivityModel(
            group_id=group.id,
            actor_id=user_id,
            activity_type="GROUP_DELETED",
            details=f"Group was archived/deleted by owner {user_id}.",
        )
        session.add(activity)

        await session.commit()

    @staticmethod
    async def transfer_ownership(
        session: AsyncSession,
        group_id: uuid.UUID,
        current_owner_id: str,
        new_owner_id: str,
    ) -> None:
        """Transfer group ownership to an existing active member. Strictly requires OWNER."""
        role = await GroupService.verify_membership(session, group_id, current_owner_id)
        if role != GroupRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the current OWNER can transfer ownership.",
            )

        if current_owner_id == new_owner_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target user is already the OWNER.",
            )

        # Verify target is an active member
        target_role = await GroupService.get_user_role(session, group_id, new_owner_id)
        if not target_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target user must be an active member of the group before receiving ownership.",
            )

        # Atomic role swap: current owner becomes ADMIN, target becomes OWNER
        await session.execute(
            select(GroupMemberModel)
            .where(and_(GroupMemberModel.group_id == group_id, GroupMemberModel.user_id == current_owner_id))
        )
        owner_member = (
            await session.execute(
                select(GroupMemberModel).where(
                    and_(GroupMemberModel.group_id == group_id, GroupMemberModel.user_id == current_owner_id)
                )
            )
        ).scalar_one()
        target_member = (
            await session.execute(
                select(GroupMemberModel).where(
                    and_(GroupMemberModel.group_id == group_id, GroupMemberModel.user_id == new_owner_id)
                )
            )
        ).scalar_one()

        owner_member.role = GroupRole.ADMIN.value
        target_member.role = GroupRole.OWNER.value

        group = (await session.execute(select(GroupModel).where(GroupModel.id == group_id))).scalar_one()
        group.created_by = new_owner_id
        group.updated_at = datetime.now(timezone.utc)

        activity = GroupActivityModel(
            group_id=group_id,
            actor_id=current_owner_id,
            activity_type="OWNERSHIP_TRANSFERRED",
            details=f"Ownership transferred from {current_owner_id} to {new_owner_id}.",
        )
        session.add(activity)

        await session.commit()

    @staticmethod
    async def add_member(
        session: AsyncSession,
        group_id: uuid.UUID,
        requester_id: str,
        target_user_id: str,
        role: str = GroupRole.MEMBER.value,
    ) -> GroupMemberModel:
        """Add a member directly to the group. Requires OWNER or ADMIN role."""
        req_role = await GroupService.verify_membership(
            session, group_id, requester_id, required_roles=[GroupRole.OWNER.value, GroupRole.ADMIN.value]
        )

        # Privilege escalation prevention:
        valid_roles = {r.value for r in GroupRole}
        if role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role '{role}'. Must be one of {valid_roles}.",
            )

        if role == GroupRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot assign OWNER role via add_member. Use transfer_ownership instead.",
            )

        if req_role == GroupRole.ADMIN.value and role == GroupRole.ADMIN.value:
            # Only OWNER can appoint new ADMINs
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the group OWNER can appoint new ADMINs.",
            )

        # Check target user existence in users table
        user_exists = (
            await session.execute(select(UserModel).where(UserModel.id == target_user_id))
        ).scalar_one_or_none()
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {target_user_id} does not exist.",
            )

        # Check duplicate membership
        existing_member = (
            await session.execute(
                select(GroupMemberModel).where(
                    and_(GroupMemberModel.group_id == group_id, GroupMemberModel.user_id == target_user_id)
                )
            )
        ).scalar_one_or_none()

        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User {target_user_id} is already a member of this group.",
            )

        new_member = GroupMemberModel(
            group_id=group_id,
            user_id=target_user_id,
            role=role,
        )
        session.add(new_member)

        activity = GroupActivityModel(
            group_id=group_id,
            actor_id=requester_id,
            activity_type="MEMBER_ADDED",
            details=f"User {target_user_id} added with role {role} by {requester_id}.",
        )
        session.add(activity)

        await session.commit()
        await session.refresh(new_member)
        return new_member

    @staticmethod
    async def update_member_role(
        session: AsyncSession,
        group_id: uuid.UUID,
        requester_id: str,
        target_user_id: str,
        new_role: str,
    ) -> GroupMemberModel:
        """Change a member's role. Enforces RBAC boundaries."""
        req_role = await GroupService.verify_membership(
            session, group_id, requester_id, required_roles=[GroupRole.OWNER.value, GroupRole.ADMIN.value]
        )

        valid_roles = {r.value for r in GroupRole}
        if new_role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role '{new_role}'. Must be one of {valid_roles}.",
            )

        if new_role == GroupRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot assign OWNER role via role change. Use transfer_ownership instead.",
            )

        target_member = (
            await session.execute(
                select(GroupMemberModel).where(
                    and_(GroupMemberModel.group_id == group_id, GroupMemberModel.user_id == target_user_id)
                )
            )
        ).scalar_one_or_none()

        if not target_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Member {target_user_id} not found in this group.",
            )

        # Cannot modify OWNER
        if target_member.role == GroupRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify the role of the group OWNER.",
            )

        # ADMINs cannot modify other ADMINs or promote to ADMIN
        if req_role == GroupRole.ADMIN.value:
            if target_member.role == GroupRole.ADMIN.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admins cannot modify fellow Admins' roles.",
                )
            if new_role == GroupRole.ADMIN.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the group OWNER can promote members to ADMIN.",
                )

        target_member.role = new_role

        activity = GroupActivityModel(
            group_id=group_id,
            actor_id=requester_id,
            activity_type="ROLE_CHANGED",
            details=f"User {target_user_id} role changed to {new_role} by {requester_id}.",
        )
        session.add(activity)

        await session.commit()
        await session.refresh(target_member)
        return target_member

    @staticmethod
    async def remove_member(
        session: AsyncSession,
        group_id: uuid.UUID,
        requester_id: str,
        target_user_id: str,
    ) -> None:
        """Remove a member from the group or leave the group."""
        req_role = await GroupService.verify_membership(session, group_id, requester_id)

        target_member = (
            await session.execute(
                select(GroupMemberModel).where(
                    and_(GroupMemberModel.group_id == group_id, GroupMemberModel.user_id == target_user_id)
                )
            )
        ).scalar_one_or_none()

        if not target_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Member {target_user_id} not found in this group.",
            )

        # Case 1: Self-leaving
        if requester_id == target_user_id:
            if target_member.role == GroupRole.OWNER.value:
                # Check if there are other members
                cnt_stmt = select(func.count(GroupMemberModel.user_id)).where(
                    and_(GroupMemberModel.group_id == group_id, GroupMemberModel.user_id != requester_id)
                )
                other_members = (await session.execute(cnt_stmt)).scalar() or 0
                if other_members > 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="OWNER must transfer ownership before leaving a group with active members.",
                    )
            await session.delete(target_member)
            await session.commit()
            return

        # Case 2: Removing someone else
        if req_role not in (GroupRole.OWNER.value, GroupRole.ADMIN.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only OWNER or ADMIN can remove other members.",
            )

        if target_member.role == GroupRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot remove the group OWNER.",
            )

        if req_role == GroupRole.ADMIN.value and target_member.role == GroupRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot remove fellow Admins.",
            )

        await session.delete(target_member)

        activity = GroupActivityModel(
            group_id=group_id,
            actor_id=requester_id,
            activity_type="MEMBER_REMOVED",
            details=f"User {target_user_id} removed by {requester_id}.",
        )
        session.add(activity)

        await session.commit()

    @staticmethod
    async def create_invitation(
        session: AsyncSession,
        group_id: uuid.UUID,
        inviter_id: str,
        invitee_email: str,
        role: str = GroupRole.MEMBER.value,
        expiry_days: int = 7,
    ) -> Tuple[GroupInvitationModel, str]:
        """Create a cryptographically secure, token-hashed invitation. Requires OWNER or ADMIN."""
        req_role = await GroupService.verify_membership(
            session, group_id, inviter_id, required_roles=[GroupRole.OWNER.value, GroupRole.ADMIN.value]
        )

        valid_roles = {r.value for r in GroupRole}
        if role not in valid_roles or role == GroupRole.OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid invitation role '{role}'. Cannot invite as OWNER.",
            )

        if req_role == GroupRole.ADMIN.value and role == GroupRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only OWNER can invite new ADMINs.",
            )

        # Generate cryptographically secure random token and SHA-256 hash
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)

        invitation = GroupInvitationModel(
            group_id=group_id,
            inviter_id=inviter_id,
            invitee_email=invitee_email.strip().lower(),
            token_hash=token_hash,
            role=role,
            status=InvitationStatus.PENDING.value,
            expires_at=expires_at,
        )
        session.add(invitation)

        activity = GroupActivityModel(
            group_id=group_id,
            actor_id=inviter_id,
            activity_type="INVITATION_CREATED",
            details=f"Invitation created for {invitee_email} as {role}.",
        )
        session.add(activity)

        await session.commit()
        await session.refresh(invitation)
        return invitation, raw_token

    @staticmethod
    async def accept_invitation(
        session: AsyncSession,
        raw_token: str,
        current_user_id: str,
    ) -> GroupMemberModel:
        """Accept an invitation using raw token. Validates hash, expiration, and status."""
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        stmt = select(GroupInvitationModel).where(GroupInvitationModel.token_hash == token_hash)
        inv = (await session.execute(stmt)).scalar_one_or_none()

        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or unrecognized invitation token.",
            )

        if inv.status != InvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invitation is no longer pending (status: {inv.status}).",
            )

        now = datetime.now(timezone.utc)
        expires_at = inv.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            inv.status = InvitationStatus.EXPIRED.value
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation has expired.",
            )

        # Check if already a member
        existing = (
            await session.execute(
                select(GroupMemberModel).where(
                    and_(GroupMemberModel.group_id == inv.group_id, GroupMemberModel.user_id == current_user_id)
                )
            )
        ).scalar_one_or_none()

        if existing:
            inv.status = InvitationStatus.ACCEPTED.value
            await session.commit()
            return existing

        new_member = GroupMemberModel(
            group_id=inv.group_id,
            user_id=current_user_id,
            role=inv.role,
        )
        session.add(new_member)
        inv.status = InvitationStatus.ACCEPTED.value

        activity = GroupActivityModel(
            group_id=inv.group_id,
            actor_id=current_user_id,
            activity_type="INVITATION_ACCEPTED",
            details=f"User {current_user_id} accepted invitation as {inv.role}.",
        )
        session.add(activity)

        await session.commit()
        await session.refresh(new_member)
        return new_member

    @staticmethod
    async def reject_invitation(
        session: AsyncSession,
        raw_token: str,
    ) -> None:
        """Reject an invitation token."""
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        stmt = select(GroupInvitationModel).where(GroupInvitationModel.token_hash == token_hash)
        inv = (await session.execute(stmt)).scalar_one_or_none()

        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or unrecognized invitation token.",
            )

        if inv.status != InvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invitation is not pending (status: {inv.status}).",
            )

        inv.status = InvitationStatus.REJECTED.value
        await session.commit()

    @staticmethod
    async def validate_invitation(
        session: AsyncSession,
        raw_token: str,
    ) -> dict:
        """Validate an invitation token and return preview metadata without consuming it."""
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        stmt = select(GroupInvitationModel).where(GroupInvitationModel.token_hash == token_hash)
        inv = (await session.execute(stmt)).scalar_one_or_none()

        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or unrecognized invitation token.",
            )

        now = datetime.now(timezone.utc)
        expires_at = inv.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            inv.status = InvitationStatus.EXPIRED.value
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation has expired.",
            )

        if inv.status != InvitationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invitation is no longer pending (status: {inv.status}).",
            )

        group_stmt = select(GroupModel).where(GroupModel.id == inv.group_id)
        group = (await session.execute(group_stmt)).scalar_one_or_none()

        return {
            "invitation_id": str(inv.id),
            "group_id": str(inv.group_id),
            "group_name": group.name if group else "Unknown Group",
            "role": inv.role,
            "invitee_email": inv.invitee_email,
            "expires_at": inv.expires_at.isoformat(),
            "status": inv.status,
        }

    @staticmethod
    async def list_pending_invitations(
        session: AsyncSession, group_id: uuid.UUID, requester_id: str
    ) -> List[GroupInvitationResponse]:
        """List pending invitations for a group. Requires OWNER or ADMIN."""
        await GroupService.verify_membership(
            session, group_id, requester_id, required_roles=[GroupRole.OWNER.value, GroupRole.ADMIN.value]
        )

        group_name = (
            await session.execute(select(GroupModel.name).where(GroupModel.id == group_id))
        ).scalar_one_or_none()

        stmt = (
            select(GroupInvitationModel)
            .where(
                and_(
                    GroupInvitationModel.group_id == group_id,
                    GroupInvitationModel.status == InvitationStatus.PENDING.value,
                )
            )
            .order_by(GroupInvitationModel.created_at.desc())
        )
        invs = (await session.execute(stmt)).scalars().all()

        return [
            GroupInvitationResponse(
                id=inv.id,
                group_id=inv.group_id,
                group_name=group_name,
                inviter_id=inv.inviter_id,
                invitee_email=inv.invitee_email,
                role=inv.role,
                status=inv.status,
                expires_at=inv.expires_at,
                created_at=inv.created_at,
            )
            for inv in invs
        ]

    @staticmethod
    async def revoke_invitation(
        session: AsyncSession, invitation_id: uuid.UUID, requester_id: str
    ) -> None:
        """Revoke a pending invitation. Requires OWNER or ADMIN."""
        stmt = select(GroupInvitationModel).where(GroupInvitationModel.id == invitation_id)
        inv = (await session.execute(stmt)).scalar_one_or_none()
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found.",
            )

        await GroupService.verify_membership(
            session, inv.group_id, requester_id, required_roles=[GroupRole.OWNER.value, GroupRole.ADMIN.value]
        )

        inv.status = InvitationStatus.REVOKED.value
        await session.commit()

    @staticmethod
    async def search_users(
        session: AsyncSession, query_str: str, limit: int = 10
    ) -> List[UserModel]:
        """Privacy-conscious user lookup by username prefix or substring."""
        clean_q = query_str.strip().lower()
        if not clean_q or len(clean_q) < 2:
            return []

        stmt = (
            select(UserModel)
            .where(func.lower(UserModel.username).contains(clean_q))
            .limit(limit)
        )
        res = await session.execute(stmt)
        return res.scalars().all()
