"""Module 6 - Multi-Channel Send: LinkedIn task queue, WhatsApp/LinkedIn/email message log, tracking."""
from app.models._common import *  # noqa: F401,F403


class ChannelMessage(Base, TimestampMixin):
    __tablename__ = "channel_messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_businesses.id", ondelete="SET NULL"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20))            # email | whatsapp | linkedin
    direction: Mapped[str] = mapped_column(String(10), default="outbound")
    to_address: Mapped[str] = mapped_column(String(255))
    subject: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | sent | delivered | read | failed | simulated | received
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)


class LinkedInTask(Base, TimestampMixin):
    __tablename__ = "linkedin_tasks"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_businesses.id", ondelete="SET NULL"), nullable=True)
    profile_url: Mapped[str] = mapped_column(String(500))
    contact_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    action: Mapped[str] = mapped_column(String(20), default="connect")  # connect | message | follow_up
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="queued")   # queued | in_progress | done | skipped | failed
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class TrackedEmail(Base, TimestampMixin):
    __tablename__ = "tracked_emails"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_businesses.id", ondelete="SET NULL"), nullable=True)
    token: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    recipient: Mapped[str] = mapped_column(String(255))
    subject: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    sent_via: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="sent")
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    first_opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class TrackingEvent(Base, TimestampMixin):
    __tablename__ = "tracking_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    tracked_email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tracked_emails.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(10))  # open | click
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)

