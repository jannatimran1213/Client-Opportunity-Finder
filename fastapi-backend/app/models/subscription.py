"""
Module 1 - Subscription Engine: one subscription per workspace + monthly usage counters
that the plan limits (app/services/billing/plans.py) are enforced against.
"""
from app.models._common import *  # noqa: F401,F403


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(30), default="basic")         # basic | pro | enterprise
    interval: Mapped[str] = mapped_column(String(10), default="monthly")   # monthly | yearly
    status: Mapped[str] = mapped_column(String(30), default="trialing")    # trialing | active | past_due | canceled
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_mode: Mapped[str] = mapped_column(String(10), default="test")  # test (mock) | live (Stripe)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)


class WorkspaceUsage(Base, TimestampMixin):
    __tablename__ = "workspace_usage"
    __table_args__ = (UniqueConstraint("workspace_id", "period", "metric", name="uq_usage_metric"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = ws_fk()
    period: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    metric: Mapped[str] = mapped_column(String(40))             # emails | ai_generations | audits | whatsapp | linkedin
    count: Mapped[int] = mapped_column(Integer, default=0)

