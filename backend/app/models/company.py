from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    __table_args__ = (
        UniqueConstraint("exchange", "ticker"),
        Index("ix_companies_name", "name"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    ticker: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    exchange: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    isin: Mapped[str | None] = mapped_column(
        String(12),
        nullable=True,
        unique=True,
    )
    website: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
