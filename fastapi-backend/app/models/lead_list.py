"""Module 3 - Lead Management: lists, list membership, lead status/tags and validation results."""
from app.models._common import *  # noqa: F401,F403


class LeadList(Base, TimestampMixin):
    __tablename__ = "lead_lists"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(20), default="#6D5DF6")

    items = relationship("LeadListItem", back_populates="lead_list", cascade="all, delete-orphan")


class LeadListItem(Base, TimestampMixin):
    __tablename__ = "lead_list_items"
    __table_args__ = (UniqueConstraint("list_id", "business_id", name="uq_list_business"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lead_lists.id", ondelete="CASCADE"), index=True)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_businesses.id", ondelete="CASCADE"), index=True)

    lead_list = relationship("LeadList", back_populates="items")


class LeadProfile(Base, TimestampMixin):
    """Pipeline status, tags and priority for a saved business (1-to-1)."""
    __tablename__ = "lead_profiles"

    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_businesses.id", ondelete="CASCADE"), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    status: Mapped[str] = mapped_column(String(30), default="new")  # new | contacted | replied | meeting | won | lost
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    whatsapp_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    # Validation filter results
    email_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)    # valid | invalid | risky | unknown
    email_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    phone_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    phone_e164: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    website_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # reachable | unreachable | missing
    website_http_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    validation_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

