"""Module 5 - AI Copywriter: every generated icebreaker / email / reply / industry piece is stored."""
from app.models._common import *  # noqa: F401,F403


class CopyDraft(Base, TimestampMixin):
    __tablename__ = "copy_drafts"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_businesses.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(30))       # icebreaker | email | reply | industry_content
    channel: Mapped[str] = mapped_column(String(20), default="email")  # email | linkedin | whatsapp | web
    industry: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    body: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    source: Mapped[str] = mapped_column(String(20), default="template")  # llm | template

