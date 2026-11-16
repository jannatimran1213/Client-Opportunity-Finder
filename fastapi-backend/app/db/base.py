from datetime import datetime
from typing import Any

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    id: Any
    __name__: str


class TimestampMixin:
    """Mixin to add created_at and updated_at columns."""
    # Fetch server-generated timestamps back with RETURNING on INSERT *and* UPDATE, so reading
    # updated_at after a commit never triggers a lazy load (which async sessions can't do).
    __mapper_args__ = {"eager_defaults": True}
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), nullable=False
    )

