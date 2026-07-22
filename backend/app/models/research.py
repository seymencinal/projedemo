from enum import StrEnum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ResearchStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Research(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "researches"
    __table_args__ = (Index("ix_researches_organization_id", "organization_id"),)

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ResearchStatus] = mapped_column(
        Enum(
            ResearchStatus,
            name="research_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=ResearchStatus.DRAFT,
    )
