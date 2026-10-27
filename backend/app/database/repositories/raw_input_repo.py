import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.raw_input import RawInputModel
from app.database.repositories.base import BaseRepository


class RawInputRepository(BaseRepository[RawInputModel]):
    """Data access repository for raw_inputs table."""

    async def create(
        self,
        media_type: str,
        raw_payload: str,
        structured_payload: dict[str, Any] | None = None,
        client_id: str = "U_DEVELOPMENT",
        group_id: str | None = None,
        status: str = "received",
        input_id: uuid.UUID | None = None,
    ) -> RawInputModel:
        """Persist a new raw input with exact text preservation."""
        record = RawInputModel(
            id=input_id or uuid.uuid4(),
            media_type=media_type,
            raw_payload=raw_payload,
            structured_payload=structured_payload,
            client_id=client_id,
            group_id=group_id,
            status=status,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_id(self, input_id: uuid.UUID | str) -> RawInputModel | None:
        """Retrieve raw input record by primary key."""
        target_id = input_id if isinstance(input_id, uuid.UUID) else uuid.UUID(str(input_id))
        result = await self.session.execute(
            select(RawInputModel).where(RawInputModel.id == target_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        input_id: uuid.UUID | str,
        status: str,
        error_message: str | None = None,
    ) -> RawInputModel | None:
        """Update processing status and optional error message."""
        record = await self.get_by_id(input_id)
        if record is not None:
            record.status = status
            if error_message is not None:
                record.error_message = error_message
            await self.session.flush()
        return record

    async def mark_completed(self, input_id: uuid.UUID | str) -> RawInputModel | None:
        """Mark raw input status as completed."""
        return await self.update_status(input_id, status="completed")

    async def mark_failed(
        self,
        input_id: uuid.UUID | str,
        error_message: str,
    ) -> RawInputModel | None:
        """Mark raw input status as failed with error details."""
        return await self.update_status(
            input_id,
            status="failed",
            error_message=error_message,
        )

    async def get_feed(
        self,
        limit: int = 200,
        offset: int = 0,
    ) -> list[RawInputModel]:
        """Retrieve raw inputs ordered by received_at DESC for user feed."""
        stmt = (
            select(RawInputModel)
            .order_by(RawInputModel.received_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_total_count(self) -> int:
        """Count total raw inputs in database."""
        from sqlalchemy import func

        result = await self.session.execute(select(func.count(RawInputModel.id)))
        return result.scalar() or 0
