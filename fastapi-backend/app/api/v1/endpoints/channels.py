"""
Module 6 - Multi-Channel Send.

  Connect Gmail & Business Email ... /email-accounts/* (Google OAuth + SMTP, existing module, now registered)
                                     POST /channels/email/send, /channels/email/send-batch (tracked sending)
  LinkedIn Automation .............. /channels/linkedin/* (assisted task queue with daily limit)
  WhatsApp API Integration ......... POST /channels/whatsapp/send, GET/POST /channels/whatsapp/webhook
  Tracking Pixel Engine ............ /track/o/{token}.gif, /track/c/{token} (public) + GET /channels/tracking
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenancy import WorkspaceContext, get_workspace_context, lead_scope, require_permission
from app.api.v1.endpoints.businesses import _biz_to_dict
from app.core.config import settings
from app.core.security import security_manager
from app.db.session import get_db
from app.models.channel import ChannelMessage, LinkedInTask, TrackedEmail, TrackingEvent
from app.models.copy_draft import CopyDraft
from app.models.email_account import EmailAccount
from app.models.lead_list import LeadListItem, LeadProfile
from app.models.saved_business import SavedBusiness
from app.services.billing.plans import enforce_limit, record_usage
from app.services.channels import linkedin, tracking, whatsapp

router = APIRouter()
public_router = APIRouter()


# â”€â”€ Schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class EmailSendIn(BaseModel):
    to: str
    subject: str
    body: str
    html: Optional[str] = None
    business_id: Optional[str] = None
    account_id: Optional[str] = None
    track_opens: bool = True
    track_clicks: bool = True


class BatchSendIn(BaseModel):
    batch_id: Optional[str] = None
    draft_ids: List[str] = []
    account_id: Optional[str] = None
    delay_seconds: float = 2.0


class WhatsAppIn(BaseModel):
    to: Optional[str] = None
    body: str = ""
    business_id: Optional[str] = None
    template_name: Optional[str] = None
    template_language: str = "en_US"
    template_params: List[str] = []


class LinkedInTaskIn(BaseModel):
    profile_url: Optional[str] = None
    business_id: Optional[str] = None
    contact_name: Optional[str] = None
    action: str = "connect"
    message: Optional[str] = None
    scheduled_for: Optional[datetime] = None


class LinkedInQueueIn(BaseModel):
    business_ids: List[str] = []
    list_id: Optional[str] = None
    action: str = "connect"
    template: Optional[str] = None


class LinkedInUpdate(BaseModel):
    status: Optional[str] = None
    message: Optional[str] = None
    profile_url: Optional[str] = None


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _lead(db: AsyncSession, ctx: WorkspaceContext, business_id: Optional[str]) -> Optional[SavedBusiness]:
    if not business_id:
        return None
    b = (await db.execute(select(SavedBusiness).where(SavedBusiness.id == uuid.UUID(business_id), lead_scope(ctx)))).scalars().first()
    if not b:
        raise HTTPException(status_code=404, detail="Lead not found")
    return b


async def _mark_contacted(db: AsyncSession, ctx: WorkspaceContext, b: Optional[SavedBusiness]):
    if not b:
        return
    p = await db.get(LeadProfile, b.id)
    if not p:
        db.add(LeadProfile(business_id=b.id, workspace_id=ctx.workspace.id, status="contacted", tags=[]))
    elif p.status in (None, "new"):
        p.status = "contacted"


async def send_tracked_email(db: AsyncSession, ctx: WorkspaceContext, *, to: str, subject: str, body: str,
                             html: Optional[str] = None, business: Optional[SavedBusiness] = None,
                             account_id: Optional[str] = None, track_opens: bool = True, track_clicks: bool = True) -> dict:
    """Send through the user's connected Gmail/SMTP account (or Resend fallback) with open + click tracking."""
    await enforce_limit(db, ctx.workspace.id, "emails")
    token = tracking.new_token()
    html_body = html or tracking.text_to_html(body)
    if track_opens or track_clicks:
        html_body = tracking.instrument_html(html_body, token, track_clicks=track_clicks, track_opens=track_opens)

    q = select(EmailAccount).where(EmailAccount.user_id == ctx.user.id, EmailAccount.is_active == True)  # noqa: E712
    if account_id:
        q = q.where(EmailAccount.id == uuid.UUID(account_id))
    accounts = (await db.execute(q.order_by(EmailAccount.is_default.desc()))).scalars().all()
    via, result = None, None
    if accounts:
        from app.services.email.account_manager import send_via_account
        acct = accounts[0]
        result = await send_via_account(acct, to, subject, body, html_body)
        via = f"{acct.provider}:{acct.email_address}"
    else:
        from app.services.email.resend_sender import is_configured, send_email as resend_send
        if not is_configured():
            raise HTTPException(status_code=400, detail="Connect a Gmail or SMTP email account first (Channels page)")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: resend_send(to_email=to, subject=subject, body=body, html_body=html_body))
        via = "resend"
    ok = bool(result and result.get("success"))
    msg = ChannelMessage(workspace_id=ctx.workspace.id, business_id=business.id if business else None, channel="email",
                         to_address=to, subject=subject, body=body, status="sent" if ok else "failed",
                         provider_message_id=(result or {}).get("message_id"), error=None if ok else (result or {}).get("error"),
                         meta={"via": via, "tracking_token": token})
    db.add(msg)
    te = None
    if ok:
        te = TrackedEmail(workspace_id=ctx.workspace.id, business_id=business.id if business else None, token=token,
                          recipient=to, subject=subject, sent_via=via, status="sent")
        db.add(te)
        await _mark_contacted(db, ctx, business)
    await db.commit()
    if ok:
        await record_usage(db, ctx.workspace.id, "emails")
    return {"success": ok, "via": via, "error": None if ok else (result or {}).get("error"),
            "tracking_id": str(te.id) if te else None, "message_id": str(msg.id)}


# â”€â”€ Status â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/status")
async def status(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    from app.services.email.resend_sender import is_configured
    accounts = (await db.execute(select(EmailAccount).where(EmailAccount.user_id == ctx.user.id))).scalars().all()
    return {
        "email": {"accounts": [{"id": str(a.id), "provider": a.provider, "email": a.email_address, "is_default": a.is_default,
                                "status": a.connection_status} for a in accounts],
                  "google_oauth_ready": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
                  "resend_fallback": is_configured()},
        "whatsapp": {"configured": whatsapp.configured(), "mode": "live" if whatsapp.configured() else "simulated (wa.me links)",
                     "webhook_url": f"{settings.BACKEND_URL}/api/v1/channels/whatsapp/webhook"},
        "linkedin": {"mode": "assisted", "daily_limit": settings.LINKEDIN_DAILY_LIMIT},
        "tracking": {"base_url": tracking.tracking_base()},
    }


# â”€â”€ Email â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/email/send")
async def email_send(body: EmailSendIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("outreach:send"))):
    b = await _lead(db, ctx, body.business_id)
    res = await send_tracked_email(db, ctx, to=body.to, subject=body.subject, body=body.body, html=body.html, business=b,
                                   account_id=body.account_id, track_opens=body.track_opens, track_clicks=body.track_clicks)
    if not res["success"]:
        raise HTTPException(status_code=502, detail=res["error"] or "Send failed")
    return res


@router.post("/email/send-batch")
async def email_send_batch(body: BatchSendIn, db: AsyncSession = Depends(get_db),
                           ctx: WorkspaceContext = Depends(require_permission("outreach:send"))):
    q = select(CopyDraft).where(CopyDraft.workspace_id == ctx.workspace.id, CopyDraft.channel == "email")
    if body.batch_id:
        q = q.where(CopyDraft.batch_id == body.batch_id)
    elif body.draft_ids:
        q = q.where(CopyDraft.id.in_([uuid.UUID(i) for i in body.draft_ids]))
    else:
        raise HTTPException(status_code=400, detail="batch_id or draft_ids required")
    drafts = (await db.execute(q)).scalars().all()
    results = []
    for d in drafts:
        to = (d.meta or {}).get("to")
        if not to:
            results.append({"draft_id": str(d.id), "success": False, "error": "Lead has no email"})
            continue
        b = await db.get(SavedBusiness, d.business_id) if d.business_id else None
        try:
            r = await send_tracked_email(db, ctx, to=to, subject=d.subject or "Quick question", body=d.body, business=b,
                                         account_id=body.account_id)
        except HTTPException as e:
            r = {"success": False, "error": e.detail}
        results.append({"draft_id": str(d.id), "to": to, **r})
        await asyncio.sleep(max(0.0, min(body.delay_seconds, 30)))  # throttle to protect sender reputation
    return {"sent": sum(1 for r in results if r.get("success")), "failed": sum(1 for r in results if not r.get("success")),
            "results": results}


# â”€â”€ WhatsApp â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/whatsapp/send")
async def whatsapp_send(body: WhatsAppIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("outreach:send"))):
    b = await _lead(db, ctx, body.business_id)
    to = body.to
    if not to and b:
        p = await db.get(LeadProfile, b.id)
        to = (p.whatsapp_number if p else None) or b.phone
    if not to or len(whatsapp.normalize(to)) < 8:
        raise HTTPException(status_code=400, detail="A WhatsApp number (with country code) is required")
    await enforce_limit(db, ctx.workspace.id, "whatsapp")
    if whatsapp.configured():
        if body.template_name:
            res = await whatsapp.send_template(to, body.template_name, body.template_language, body.template_params)
        else:
            res = await whatsapp.send_text(to, body.body)
        status_word = "sent" if res["success"] else "failed"
    else:
        res = {"success": True, "simulated": True, "click_to_chat": whatsapp.click_to_chat(to, body.body)}
        status_word = "simulated"
    msg = ChannelMessage(workspace_id=ctx.workspace.id, business_id=b.id if b else None, channel="whatsapp",
                         to_address=whatsapp.normalize(to), body=body.body or f"[template {body.template_name}]",
                         status=status_word, provider_message_id=res.get("message_id"), error=res.get("error"),
                         meta={"template": body.template_name})
    db.add(msg)
    if res.get("success"):
        await _mark_contacted(db, ctx, b)
    await db.commit()
    if res.get("success"):
        await record_usage(db, ctx.workspace.id, "whatsapp")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=f"WhatsApp: {res.get('error')}")
    return {**res, "message_id": str(msg.id), "status": status_word}


@router.get("/whatsapp/webhook", response_class=PlainTextResponse)
async def whatsapp_verify(mode: str = Query(None, alias="hub.mode"), token: str = Query(None, alias="hub.verify_token"),
                          challenge: str = Query(None, alias="hub.challenge")):
    if mode == "subscribe" and token and security_manager.constant_time_equals(token, settings.WHATSAPP_VERIFY_TOKEN):
        return challenge or ""
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()
    if not security_manager.verify_meta_signature(raw, request.headers.get("x-hub-signature-256"), settings.WHATSAPP_APP_SECRET):
        raise HTTPException(status_code=403, detail="Bad signature")
    import json
    events = whatsapp.parse_webhook(json.loads(raw or b"{}"))
    for s in events["statuses"]:
        m = (await db.execute(select(ChannelMessage).where(ChannelMessage.provider_message_id == s["id"]))).scalars().first()
        if m:
            m.status = s["status"] or m.status
            if s.get("errors"):
                m.error = str(s["errors"])[:500]
    for inc in events["incoming"]:
        prev = (await db.execute(select(ChannelMessage).where(ChannelMessage.channel == "whatsapp",
                                                              ChannelMessage.to_address == inc["from"])
                                 .order_by(ChannelMessage.created_at.desc()))).scalars().first()
        if prev:
            db.add(ChannelMessage(workspace_id=prev.workspace_id, business_id=prev.business_id, channel="whatsapp",
                                  direction="inbound", to_address=inc["from"], body=inc["text"], status="received",
                                  provider_message_id=inc["id"]))
            if prev.business_id:
                p = await db.get(LeadProfile, prev.business_id)
                if p and p.status in ("new", "contacted"):
                    p.status = "replied"
    await db.commit()
    return {"ok": True}


# â”€â”€ LinkedIn (assisted) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _task(t: LinkedInTask) -> dict:
    return {"id": str(t.id), "business_id": str(t.business_id) if t.business_id else None, "profile_url": t.profile_url,
            "contact_name": t.contact_name, "action": t.action, "message": t.message, "status": t.status,
            "scheduled_for": t.scheduled_for.isoformat() if t.scheduled_for else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None}


async def _done_today(db: AsyncSession, ws_id) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (await db.execute(select(func.count()).select_from(LinkedInTask).where(
        LinkedInTask.workspace_id == ws_id, LinkedInTask.status == "done", LinkedInTask.completed_at >= start))).scalar() or 0


@router.get("/linkedin/tasks")
async def linkedin_tasks(status: Optional[str] = None, db: AsyncSession = Depends(get_db),
                         ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    q = select(LinkedInTask).where(LinkedInTask.workspace_id == ctx.workspace.id)
    if status:
        q = q.where(LinkedInTask.status == status)
    rows = (await db.execute(q.order_by(LinkedInTask.created_at.desc()).limit(500))).scalars().all()
    done = await _done_today(db, ctx.workspace.id)
    return {"tasks": [_task(t) for t in rows], "done_today": done, "daily_limit": settings.LINKEDIN_DAILY_LIMIT,
            "remaining_today": max(0, settings.LINKEDIN_DAILY_LIMIT - done)}


@router.get("/linkedin/next")
async def linkedin_next(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("outreach:send"))):
    remaining = max(0, settings.LINKEDIN_DAILY_LIMIT - await _done_today(db, ctx.workspace.id))
    now = datetime.now(timezone.utc)
    rows = (await db.execute(select(LinkedInTask).where(
        LinkedInTask.workspace_id == ctx.workspace.id, LinkedInTask.status == "queued",
        (LinkedInTask.scheduled_for.is_(None)) | (LinkedInTask.scheduled_for <= now)).order_by(LinkedInTask.created_at).limit(remaining))).scalars().all()
    return {"today": [_task(t) for t in rows], "remaining_today": remaining}


@router.post("/linkedin/tasks")
async def linkedin_create(body: LinkedInTaskIn, db: AsyncSession = Depends(get_db),
                          ctx: WorkspaceContext = Depends(require_permission("outreach:send"))):
    from app.api.v1.endpoints.copywriter import sender_for
    b = await _lead(db, ctx, body.business_id)
    lead = {**(_biz_to_dict(b) if b else {}), "contact_name": body.contact_name}
    url = body.profile_url
    if not url and b:
        p = await db.get(LeadProfile, b.id)
        url = (p.linkedin_url if p else None) or linkedin.search_url(b.business_name, b.city)
    if not url or "linkedin.com" not in url:
        raise HTTPException(status_code=400, detail="A linkedin.com profile URL is required")
    msg = body.message or linkedin.compose(body.action, lead, sender_for(ctx))
    t = LinkedInTask(workspace_id=ctx.workspace.id, business_id=b.id if b else None, profile_url=url,
                     contact_name=body.contact_name, action=body.action,
                     message=msg[:linkedin.CONNECT_NOTE_LIMIT] if body.action == "connect" else msg,
                     scheduled_for=body.scheduled_for)
    db.add(t)
    await db.commit()
    return _task(t)


@router.post("/linkedin/queue")
async def linkedin_queue(body: LinkedInQueueIn, db: AsyncSession = Depends(get_db),
                         ctx: WorkspaceContext = Depends(require_permission("outreach:send"))):
    from app.api.v1.endpoints.copywriter import sender_for
    ids = [uuid.UUID(i) for i in body.business_ids]
    if body.list_id:
        ids += list((await db.execute(select(LeadListItem.business_id).where(LeadListItem.list_id == uuid.UUID(body.list_id)))).scalars().all())
    leads = (await db.execute(select(SavedBusiness).where(SavedBusiness.id.in_(ids), lead_scope(ctx)))).scalars().all()
    sender, created = sender_for(ctx), 0
    for b in leads:
        p = await db.get(LeadProfile, b.id)
        url = (p.linkedin_url if p else None) or linkedin.search_url(b.business_name, b.city)
        db.add(LinkedInTask(workspace_id=ctx.workspace.id, business_id=b.id, profile_url=url, action=body.action,
                            message=linkedin.compose(body.action, _biz_to_dict(b), sender, body.template)))
        created += 1
    await db.commit()
    return {"queued": created}


@router.put("/linkedin/tasks/{task_id}")
async def linkedin_update(task_id: str, body: LinkedInUpdate, db: AsyncSession = Depends(get_db),
                          ctx: WorkspaceContext = Depends(require_permission("outreach:send"))):
    t = ctx.ensure(await db.get(LinkedInTask, uuid.UUID(task_id)), "Task")
    if body.status:
        if body.status not in ("queued", "in_progress", "done", "skipped", "failed"):
            raise HTTPException(status_code=400, detail="Invalid status")
        if body.status == "done" and t.status != "done":
            if await _done_today(db, ctx.workspace.id) >= settings.LINKEDIN_DAILY_LIMIT:
                raise HTTPException(status_code=429, detail="Daily LinkedIn safety limit reached; continue tomorrow")
            t.completed_at = datetime.now(timezone.utc)
            db.add(ChannelMessage(workspace_id=ctx.workspace.id, business_id=t.business_id, channel="linkedin",
                                  to_address=t.profile_url[:255], body=t.message, status="sent", meta={"action": t.action}))
            if t.business_id:
                b = await db.get(SavedBusiness, t.business_id)
                await _mark_contacted(db, ctx, b)
            await record_usage(db, ctx.workspace.id, "linkedin")
        t.status = body.status
    if body.message is not None:
        t.message = body.message
    if body.profile_url:
        t.profile_url = body.profile_url
    await db.commit()
    return _task(t)


@router.delete("/linkedin/tasks/{task_id}")
async def linkedin_delete(task_id: str, db: AsyncSession = Depends(get_db),
                          ctx: WorkspaceContext = Depends(require_permission("outreach:send"))):
    t = ctx.ensure(await db.get(LinkedInTask, uuid.UUID(task_id)), "Task")
    await db.delete(t)
    await db.commit()
    return {"message": "deleted"}


# â”€â”€ Message log + tracking dashboard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/messages")
async def messages(channel: Optional[str] = None, business_id: Optional[str] = None, db: AsyncSession = Depends(get_db),
                   ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    q = select(ChannelMessage).where(ChannelMessage.workspace_id == ctx.workspace.id)
    if channel:
        q = q.where(ChannelMessage.channel == channel)
    if business_id:
        q = q.where(ChannelMessage.business_id == uuid.UUID(business_id))
    rows = (await db.execute(q.order_by(ChannelMessage.created_at.desc()).limit(300))).scalars().all()
    return {"messages": [{"id": str(m.id), "channel": m.channel, "direction": m.direction, "to": m.to_address,
                          "subject": m.subject, "body": m.body[:500], "status": m.status, "error": m.error,
                          "business_id": str(m.business_id) if m.business_id else None,
                          "created_at": m.created_at.isoformat() if m.created_at else None} for m in rows]}


@router.get("/tracking")
async def tracking_dashboard(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    rows = (await db.execute(select(TrackedEmail).where(TrackedEmail.workspace_id == ctx.workspace.id)
                             .order_by(TrackedEmail.created_at.desc()).limit(300))).scalars().all()
    sent = len(rows)
    opened = sum(1 for r in rows if r.open_count)
    clicked = sum(1 for r in rows if r.click_count)
    return {"totals": {"sent": sent, "opened": opened, "clicked": clicked,
                       "open_rate": round(100 * opened / sent, 1) if sent else 0,
                       "click_rate": round(100 * clicked / sent, 1) if sent else 0},
            "emails": [{"id": str(r.id), "recipient": r.recipient, "subject": r.subject, "sent_via": r.sent_via,
                        "opens": r.open_count, "clicks": r.click_count,
                        "first_opened_at": r.first_opened_at.isoformat() if r.first_opened_at else None,
                        "last_event_at": r.last_event_at.isoformat() if r.last_event_at else None,
                        "sent_at": r.created_at.isoformat() if r.created_at else None} for r in rows]}


@router.get("/tracking/{tracked_id}/events")
async def tracking_events(tracked_id: str, db: AsyncSession = Depends(get_db),
                          ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    te = ctx.ensure(await db.get(TrackedEmail, uuid.UUID(tracked_id)), "Tracked email")
    ev = (await db.execute(select(TrackingEvent).where(TrackingEvent.tracked_email_id == te.id)
                           .order_by(TrackingEvent.created_at.desc()))).scalars().all()
    return {"events": [{"type": e.event_type, "url": e.url, "ip": e.ip, "user_agent": e.user_agent,
                        "at": e.created_at.isoformat() if e.created_at else None} for e in ev]}


# â”€â”€ Public tracking endpoints (no auth: they are hit by the recipient's mail client) â”€â”€

async def _record(db: AsyncSession, token: str, kind: str, request: Request, url: Optional[str] = None):
    te = (await db.execute(select(TrackedEmail).where(TrackedEmail.token == token))).scalars().first()
    if not te:
        return
    now = datetime.now(timezone.utc)
    if kind == "open":
        te.open_count = (te.open_count or 0) + 1
        te.first_opened_at = te.first_opened_at or now
        te.status = "opened" if te.status == "sent" else te.status
    else:
        te.click_count = (te.click_count or 0) + 1
        te.status = "clicked"
    te.last_event_at = now
    db.add(TrackingEvent(tracked_email_id=te.id, event_type=kind, url=url,
                         ip=(request.headers.get("x-forwarded-for") or (request.client.host if request.client else ""))[:64],
                         user_agent=(request.headers.get("user-agent") or "")[:400]))
    await db.commit()


@public_router.get("/o/{token}.gif")
async def open_pixel(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        await _record(db, token, "open", request)
    except Exception:
        pass
    return Response(content=tracking.PIXEL_GIF, media_type="image/gif",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"})


@public_router.get("/c/{token}")
async def click_redirect(token: str, request: Request, u: str = Query(...), s: str = Query(...), db: AsyncSession = Depends(get_db)):
    if not security_manager.verify_signature(f"{token}|{u}", s) or not security_manager.is_safe_redirect_url(u):
        raise HTTPException(status_code=400, detail="Invalid tracking link")
    try:
        await _record(db, token, "click", request, u)
    except Exception:
        pass
    return RedirectResponse(u, status_code=302)

