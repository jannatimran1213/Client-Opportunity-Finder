"""
Module 1 - Subscription Engine endpoints (plans, limits, usage, Stripe checkout + webhook, test mode).
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenancy import WorkspaceContext, get_workspace_context, lead_scope
from app.core.config import settings
from app.db.session import get_db
from app.models.payment_history import PaymentHistory
from app.models.saved_business import SavedBusiness
from app.models.site_page import SitePage
from app.models.subscription import Subscription
from app.models.workspace import WorkspaceMember
from app.services.billing import stripe_client
from app.services.billing.plans import DEFAULT_PLAN, INTERVALS, PLANS, get_subscription, get_usage, plan_limits, price_for, stripe_price_for

router = APIRouter()


class CheckoutIn(BaseModel):
    plan: str
    interval: str = "monthly"  # monthly | yearly


def _sub(sub: Subscription) -> dict:
    return {
        "plan": sub.plan, "plan_name": PLANS.get(sub.plan, PLANS[DEFAULT_PLAN])["name"], "status": sub.status,
        "interval": sub.interval, "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
        "billing_mode": sub.billing_mode, "cancel_at_period_end": sub.cancel_at_period_end,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "stripe_customer_id": sub.stripe_customer_id,
    }


@router.get("/plans")
async def list_plans():
    return {"plans": [{"slug": k, **v} for k, v in PLANS.items()],
            "mode": "live" if settings.billing_live else "test"}


@router.get("/subscription")
async def my_subscription(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    sub = await get_subscription(db, ctx.workspace.id)
    usage = await get_usage(db, ctx.workspace.id)
    usage["leads"] = (await db.execute(select(func.count()).select_from(SavedBusiness).where(lead_scope(ctx)))).scalar() or 0
    usage["members"] = (await db.execute(select(func.count()).select_from(WorkspaceMember).where(
        WorkspaceMember.workspace_id == ctx.workspace.id))).scalar() or 0
    usage["pages"] = (await db.execute(select(func.count()).select_from(SitePage).where(
        SitePage.workspace_id == ctx.workspace.id))).scalar() or 0
    limits = plan_limits(sub.plan)
    return {"subscription": _sub(sub), "limits": limits, "usage": usage,
            "percent": {k: (round(100 * usage.get(k, 0) / v) if v else 0) for k, v in limits.items()},
            "mode": "live" if settings.billing_live else "test"}


async def _activate(db: AsyncSession, ws_id, plan: str, user_id, mode: str, amount: float, txn: str,
                    customer_id=None, subscription_id=None, interval: str = "monthly"):
    sub = await get_subscription(db, ws_id)
    sub.plan = plan
    sub.interval = interval
    sub.status = "active"
    sub.billing_mode = mode
    sub.cancel_at_period_end = False
    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=365 if interval == "yearly" else 30)
    if customer_id:
        sub.stripe_customer_id = customer_id
    if subscription_id:
        sub.stripe_subscription_id = subscription_id
    if user_id:
        db.add(PaymentHistory(user_id=user_id, amount=amount, currency="USD", plan_name=f"{plan} ({interval})",
                              status="completed" if mode == "live" else "test", transaction_id=txn))
    await db.commit()
    return sub


@router.post("/checkout")
async def checkout(body: CheckoutIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    if not ctx.can("billing:manage"):
        raise HTTPException(status_code=403, detail="Only the workspace owner can change the plan")
    if body.plan not in PLANS or body.interval not in INTERVALS:
        raise HTTPException(status_code=400, detail="Unknown plan or interval")

    if settings.billing_live:
        price = stripe_price_for(body.plan, body.interval)
        if not price:
            raise HTTPException(status_code=500, detail=f"STRIPE_PRICE_{body.plan.upper()}_{body.interval.upper()} is not configured")
        sub = await get_subscription(db, ctx.workspace.id)
        try:
            session = await stripe_client.create_checkout_session(
                price_id=price, workspace_id=str(ctx.workspace.id), plan=f"{body.plan}:{body.interval}", email=ctx.user.email,
                success_url=f"{settings.FRONTEND_URL}/billing?status=success",
                cancel_url=f"{settings.FRONTEND_URL}/billing?status=cancelled",
                customer_id=sub.stripe_customer_id,
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Stripe error: {e}")
        return {"mode": "live", "checkout_url": session.get("url"), "session_id": session.get("id")}

    # Payment-gateway simulation (test mode): no card needed, plan switches immediately and a test payment is recorded
    sub = await _activate(db, ctx.workspace.id, body.plan, ctx.user.id, "test", price_for(body.plan, body.interval),
                          f"test_{uuid.uuid4().hex[:12]}", interval=body.interval)
    return {"mode": "test", "activated": True, "subscription": _sub(sub)}


@router.post("/cancel")
async def cancel(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    if not ctx.can("billing:manage"):
        raise HTTPException(status_code=403, detail="Only the workspace owner can cancel")
    sub = await get_subscription(db, ctx.workspace.id)
    if sub.billing_mode == "live" and sub.stripe_subscription_id and settings.STRIPE_SECRET_KEY:
        try:
            await stripe_client.cancel_subscription(sub.stripe_subscription_id)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Stripe error: {e}")
        sub.cancel_at_period_end = True
    else:
        sub.status = "canceled"
        sub.cancel_at_period_end = True
    await db.commit()
    return {"subscription": _sub(sub)}


@router.post("/portal")
async def portal(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    sub = await get_subscription(db, ctx.workspace.id)
    if not (settings.billing_live and sub.stripe_customer_id):
        raise HTTPException(status_code=400, detail="Customer portal is available after a live Stripe checkout")
    session = await stripe_client.create_portal_session(sub.stripe_customer_id, f"{settings.FRONTEND_URL}/billing")
    return {"url": session.get("url")}


@router.get("/payments")
async def payments(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    rows = (await db.execute(select(PaymentHistory).where(PaymentHistory.user_id == ctx.user.id)
                             .order_by(PaymentHistory.created_at.desc()).limit(50))).scalars().all()
    return {"payments": [{"id": str(p.id), "amount": float(p.amount), "currency": p.currency, "plan": p.plan_name,
                          "status": p.status, "transaction_id": p.transaction_id,
                          "date": p.created_at.isoformat() if p.created_at else None} for p in rows]}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Stripe webhook: point Stripe at {BACKEND_URL}/api/v1/billing/webhook."""
    payload = await request.body()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="STRIPE_WEBHOOK_SECRET not configured")
    if not stripe_client.verify_webhook_signature(payload, request.headers.get("stripe-signature", ""), settings.STRIPE_WEBHOOK_SECRET):
        raise HTTPException(status_code=400, detail="Invalid signature")
    event = json.loads(payload)
    etype = event.get("type")
    obj = event.get("data", {}).get("object", {})
    meta = obj.get("metadata") or {}
    ws_id = meta.get("workspace_id") or obj.get("client_reference_id")

    if etype == "checkout.session.completed" and ws_id:
        plan, _, interval = (meta.get("plan") or "pro:monthly").partition(":")
        await _activate(db, uuid.UUID(ws_id), plan, None, "live", (obj.get("amount_total") or 0) / 100,
                        obj.get("id"), obj.get("customer"), obj.get("subscription"), interval=interval or "monthly")
    elif etype in ("customer.subscription.updated", "customer.subscription.deleted"):
        sub = (await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == obj.get("id")))).scalars().first()
        if sub:
            if etype.endswith("deleted"):
                sub.status = "canceled"
            else:
                sub.status = obj.get("status", sub.status)
                sub.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
                if obj.get("current_period_end"):
                    sub.current_period_end = datetime.fromtimestamp(obj["current_period_end"], tz=timezone.utc)
            await db.commit()
    elif etype == "invoice.payment_failed":
        sub = (await db.execute(select(Subscription).where(Subscription.stripe_customer_id == obj.get("customer")))).scalars().first()
        if sub:
            sub.status = "past_due"
            await db.commit()
    return {"received": True}

