"""Module 8 - Drag-and-Drop Builder: pages/emails built from blocks, published to a subdomain."""
from app.models._common import *  # noqa: F401,F403


class SitePage(Base, TimestampMixin):
    __tablename__ = "site_pages"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_businesses.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(10), default="page")  # page | email
    template_key: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    blocks: Mapped[list] = mapped_column(JSONB, default=list)
    theme: Mapped[dict] = mapped_column(JSONB, default=dict)
    subdomain: Mapped[Optional[str]] = mapped_column(String(63), unique=True, index=True, nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    published_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)

