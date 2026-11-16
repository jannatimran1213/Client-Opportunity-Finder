"""Background jobs (Celery + Redis, with in-process fallback): scraping, audits, bulk sends, validation."""
from app.models._common import *  # noqa: F401,F403


class BackgroundJob(Base, TimestampMixin):
    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | running | completed | failed
    runner: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # celery | in-process
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

