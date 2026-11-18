"""
Module 1 - Subscription Engine: plan catalogue, limits and usage enforcement.
"""
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.subscription import Subscription, WorkspaceUsage

# Tiers from the project spec: Basic, Pro, Enterprise - billed monthly or yearly (yearly = 2 months free).
PLANS: Dict[str, dict] = {
    "basic": {
        "name": "Basic", "price": 19, "price_yearly": 190, "currency": "USD", "trial_days": 14,
        "description": "For freelancers starting outreach",
        "limits": {"leads": 500, "members": 2, "pages": 2, "emails": 500, "ai_generations": 300,
                   "audits": 100, "whatsapp": 100, "linkedin": 150},
        "features": ["Business finder + scraper", "Lead lists & validation", "Advanced + trust audits",
                     "AI copywriter (300/mo)", "2 hosted pages", "2 team seats"],
    },
    "pro": {
        "name": "Pro", "price": 49, "price_yearly": 490, "currency": "USD", "trial_days": 0,
        "description": "For small agencies",
        "limits": {"leads": 5000, "members": 5, "pages": 10, "emails": 5000, "ai_generations": 2000,
                   "audits": 1000, "whatsapp": 1500, "linkedin": 600},
        "features": ["Everything in Basic", "5 team seats", "Bulk AI emails", "WhatsApp + LinkedIn",
                     "10 hosted pages", "Open/click tracking", "Competitor benchmarking"],
    },
    "enterprise": {
        "name": "Enterprise", "price": 149, "price_yearly": 1490, "currency": "USD", "trial_days": 0,
        "description": "For teams running outreach for many clients",
        "limits": {"leads": 100000, "members": 50, "pages": 200, "emails": 50000, "ai_generations": 20000,
                   "audits": 10000, "whatsapp": 20000, "linkedin": 3000},
        "features": ["Everything in Pro", "50 team seats", "200 hosted pages", "Priority background workers",
                     "Priority support"],
    },
}
DEFAULT_PLAN = "basic"
INTERVALS = ("monthly", "yearly")

METERED = ["emails", "ai_generations", "audits", "whatsapp", "linkedin"]


def current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def stripe_price_for(plan: str, interval: str = "monthly") -> Optional[str]:
    """Env: STRIPE_PRICE_BASIC_MONTHLY, STRIPE_PRICE_BASIC_YEARLY, STRIPE_PRICE_PRO_MONTHLY, ... ENTERPRISE_YEARLY"""
    return getattr(settings, f"STRIPE_PRICE_{plan.upper()}_{interval.upper()}", None)


def price_for(plan: str, interval: str = "monthly") -> float:
    p = PLANS.get(plan, PLANS[DEFAULT_PLAN])
    return p["price_yearly"] if interval == "yearly" else p["price"]


async def get_subscription(db: AsyncSession, workspace_id) -> Subscription:
    sub = (await db.execute(select(Subscription).where(Subscription.workspace_id == workspace_id))).scalars().first()
    if not sub:
        sub = Subscription(workspace_id=workspace_id, plan=DEFAULT_PLAN, status="trialing", billing_mode="test", interval="monthly")
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
    return sub


def plan_limits(plan: str) -> Dict[str, int]:
    return PLANS.get(plan, PLANS[DEFAULT_PLAN])["limits"]


async def get_usage(db: AsyncSession, workspace_id) -> Dict[str, int]:
    rows = (await db.execute(
        select(WorkspaceUsage).where(WorkspaceUsage.workspace_id == workspace_id, WorkspaceUsage.period == current_period())
    )).scalars().all()
    usage = {m: 0 for m in METERED}
    for r in rows:
        usage[r.metric] = r.count
    return usage


async def record_usage(db: AsyncSession, workspace_id, metric: str, amount: int = 1) -> None:
    period = current_period()
    row = (await db.execute(select(WorkspaceUsage).where(
        WorkspaceUsage.workspace_id == workspace_id, WorkspaceUsage.period == period, WorkspaceUsage.metric == metric
    ))).scalars().first()
    if row:
        row.count = (row.count or 0) + amount
    else:
        db.add(WorkspaceUsage(workspace_id=workspace_id, period=period, metric=metric, count=amount))
    await db.commit()


async def enforce_limit(db: AsyncSession, workspace_id, metric: str, amount: int = 1, current: Optional[int] = None) -> None:
    """Raise HTTP 402 when the action would push the workspace over its plan limit."""
    sub = await get_subscription(db, workspace_id)
    limits = plan_limits(DEFAULT_PLAN if sub.status in ("past_due", "canceled") else sub.plan)
    limit = limits.get(metric)
    if limit is None:
        return
    if current is None:
        current = (await get_usage(db, workspace_id)).get(metric, 0)
    if current + amount > limit:
        raise HTTPException(
            status_code=402,
            detail=f"Plan limit reached: {metric} {current}/{limit} on the {PLANS.get(sub.plan, PLANS[DEFAULT_PLAN])['name']} plan. Upgrade in Billing.",
        )

