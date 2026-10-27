import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.models.base import Base, GUID

if TYPE_CHECKING:
    from app.database.models.phase1_output import Phase1OutputModel


class RawInputModel(Base):
    """Stores verbatim original user input before any AI/Phase processing.
    
    Ensures exact preservation via the `raw_payload` text field, while also
    maintaining structured metadata and JSON copy for querying.
    """
    __tablename__ = "raw_inputs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    media_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    raw_payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Exact original raw payload/text as received from user",
    )
    structured_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        comment="Optional structured copy for querying",
    )
    client_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="U_DEVELOPMENT",
        index=True,
    )
    group_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="received",
        index=True,
        comment="Processing status: received, processing, completed, failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship to downstream phase outputs
    phase1_outputs: Mapped[list["Phase1OutputModel"]] = relationship(
        "Phase1OutputModel",
        back_populates="raw_input",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<RawInputModel(id={self.id}, media_type={self.media_type}, status={self.status})>"
