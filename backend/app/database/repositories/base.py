from typing import Generic, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository providing shared async session handling."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
