"""Module 4 - Advanced Audit: speed & security, tech stack, mobile score, competitor benchmarks."""
from app.models._common import *  # noqa: F401,F403


class AdvancedAudit(Base, TimestampMixin):
    __tablename__ = "advanced_audits"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_businesses.id", ondelete="SET NULL"), nullable=True, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    security_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mobile_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    seo_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)       # indexing checks
    trust_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)     # Trust & Conversion Leak Detector
    leak_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tech_stack: Mapped[list] = mapped_column(JSONB, default=list)
    report: Mapped[dict] = mapped_column(JSONB, default=dict)


class CompetitorBenchmark(Base, TimestampMixin):
    __tablename__ = "competitor_benchmarks"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    competitor_urls: Mapped[list] = mapped_column(JSONB, default=list)
    ranking: Mapped[list] = mapped_column(JSONB, default=list)
    insights: Mapped[list] = mapped_column(JSONB, default=list)

