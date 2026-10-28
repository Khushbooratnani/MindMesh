from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base


class LocationModel(Base):
    """Stores canonical geographic locations and places."""
    __tablename__ = "locations"

    location_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    normalized_name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(512), nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    admin_area: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), default="locationiq", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    memory_links: Mapped[list["MemoryLocationModel"]] = relationship(
        "MemoryLocationModel",
        back_populates="location",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MemoryLocationModel(Base):
    """Maps memories to resolved geographic locations."""
    __tablename__ = "memory_locations"

    memory_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("phase1_outputs.memory_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    location_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("locations.location_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(64), default="extraction", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship to canonical location
    location: Mapped["LocationModel"] = relationship(
        "LocationModel",
        back_populates="memory_links",
        lazy="selectin",
    )
