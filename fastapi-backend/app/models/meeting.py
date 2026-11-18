"""Module 7 - Schedule Meeting: meetings, reminders, follow-ups, next steps, in-app notifications."""
from app.models._common import *  # noqa: F401,F403


class Meeting(Base, TimestampMixin):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_businesses.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str] = mapped_column(String(60), default="UTC")
    location: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    meeting_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    attendee_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    attendee_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attendee_phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled | completed | cancelled | no_show
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    reminders = relationship("Reminder", back_populates="meeting", cascade="all, delete-orphan")


class Reminder(Base, TimestampMixin):
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    meeting_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=True, index=True)
    follow_up_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("follow_ups.id", ondelete="CASCADE"), nullable=True)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="in_app")  # in_app | email | whatsapp
    recipient: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    meeting = relationship("Meeting", back_populates="reminders")


class FollowUp(Base, TimestampMixin):
    __tablename__ = "follow_ups"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_businesses.id", ondelete="SET NULL"), nullable=True, index=True)
    meeting_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(20), default="email")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | done | skipped
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class NextStep(Base, TimestampMixin):
    __tablename__ = "next_steps"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_businesses.id", ondelete="SET NULL"), nullable=True, index=True)
    meeting_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    owner: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    stage: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # proposal | negotiation | contract | onboarding
    done: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)

