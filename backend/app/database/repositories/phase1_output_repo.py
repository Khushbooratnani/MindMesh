import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.phase1_output import Phase1OutputModel
from app.database.repositories.base import BaseRepository


class Phase1OutputRepository(BaseRepository[Phase1OutputModel]):
    """Data access repository for phase1_outputs table."""

    async def create(
        self,
        raw_input_id: uuid.UUID | str,
        memory_id: str,
        payload: dict[str, Any],
        schema_version: str = "1.0",
        processing_status: str = "completed",
        extractor_model: str | None = None,
        output_id: uuid.UUID | None = None,
    ) -> Phase1OutputModel:
        """Persist complete validated MemoryV1 JSONB linked to raw_input_id."""
        target_raw_id = (
            raw_input_id if isinstance(raw_input_id, uuid.UUID) else uuid.UUID(str(raw_input_id))
        )
        record = Phase1OutputModel(
            id=output_id or uuid.uuid4(),
            raw_input_id=target_raw_id,
            memory_id=memory_id,
            schema_version=schema_version,
            payload=payload,
            processing_status=processing_status,
            extractor_model=extractor_model,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_id(self, output_id: uuid.UUID | str) -> Phase1OutputModel | None:
        """Retrieve phase1 output record by primary key."""
        target_id = output_id if isinstance(output_id, uuid.UUID) else uuid.UUID(str(output_id))
        result = await self.session.execute(
            select(Phase1OutputModel).where(Phase1OutputModel.id == target_id)
        )
        return result.scalar_one_or_none()

    async def get_by_memory_id(self, memory_id: str) -> Phase1OutputModel | None:
        """Retrieve phase1 output record by memory_id (e.g. M_<uuid>)."""
        result = await self.session.execute(
            select(Phase1OutputModel).where(Phase1OutputModel.memory_id == memory_id)
        )
        return result.scalar_one_or_none()

    async def get_by_raw_input_id(self, raw_input_id: uuid.UUID | str) -> list[Phase1OutputModel]:
        """Retrieve all phase1 outputs associated with a given raw input."""
        target_raw_id = (
            raw_input_id if isinstance(raw_input_id, uuid.UUID) else uuid.UUID(str(raw_input_id))
        )
        result = await self.session.execute(
            select(Phase1OutputModel).where(Phase1OutputModel.raw_input_id == target_raw_id)
        )
        return list(result.scalars().all())
