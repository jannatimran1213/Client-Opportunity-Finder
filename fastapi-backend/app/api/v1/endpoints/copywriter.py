"""
Module 5 - AI Copywriter endpoints.

  POST /copywriter/icebreakers        Personalized Icebreakers
  POST /copywriter/bulk               Bulk Email Generation (a list / selected leads -> drafts)
  POST /copywriter/reply              Dynamic Reply Assistant
  POST /copywriter/industry-content   Industry-Specific Content
  GET  /copywriter/industries, /copywriter/status, /copywriter/drafts
"""
import asyncio
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenancy import WorkspaceContext, get_workspace_context, lead_scope, require_permission
from app.api.v1.endpoints.businesses import _biz_to_dict
from app.db.session import get_db
from app.models.advanced_audit import AdvancedAudit
from app.models.copy_draft import CopyDraft
from app.models.lead_list import LeadListItem
from app.models.saved_business import SavedBusiness
from app.services.billing.plans import enforce_limit, record_usage
from app.services.copywriter import engine, llm
from app.services.copywriter.industries import CONTENT_TYPES, INDUSTRIES

router = APIRouter()


class IcebreakerIn(BaseModel):
    business_id: Optional[str] = None
    lead: Optional[Dict[str, Any]] = None
    count: int = 3
    tone: str = "friendly"


class BulkIn(BaseModel):
    business_ids: List[str] = []
    list_id: Optional[str] = None
    channel: str = "email"
    tone: str = "professional"
    industry: Optional[str] = None
    instructions: str = ""
    use_icebreaker: bool = True


class ReplyIn(BaseModel):
    message: str
    business_id: Optional[str] = None
    history: List[Dict[str, str]] = []
    instruction: str = ""


class IndustryIn(BaseModel):
    industry: str = "generic"
    content_type: str = "cold_email"
    business_id: Optional[str] = None
    tone: str = "professional"


class DraftUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None


def sender_for(ctx: WorkspaceContext) -> Dict[str, str]:
    ws = ctx.workspace
    st = ws.settings or {}
    return {"name": ctx.user.full_name, "company": ws.company_name or ws.name, "services": ws.services or "",
            "booking_link": st.get("booking_link", "")}


async def _lead_and_audit(db: AsyncSession, ctx: WorkspaceContext, business_id: Optional[str]):
    if not business_id:
        return None, None
    b = (await db.execute(select(SavedBusiness).where(SavedBusiness.id == uuid.UUID(business_id), lead_scope(ctx)))).scalars().first()
    if not b:
        raise HTTPException(status_code=404, detail="Lead not found")
    a = (await db.execute(select(AdvancedAudit).where(AdvancedAudit.business_id == b.id)
                          .order_by(AdvancedAudit.created_at.desc()))).scalars().first()
    audit = None
    if a:
        rep = a.report or {}
        audit = {"overall_score": a.overall_score, "speed_score": a.speed_score, "security_score": a.security_score,
                 "mobile_score": a.mobile_score, "seo_score": a.seo_score, "trust_score": a.trust_score,
                 "tech_stack": a.tech_stack, "leaks": [l["title"] for l in (rep.get("trust") or {}).get("leaks", [])[:4]],
                 "opportunities": rep.get("opportunities") or []}
    return b, audit


def _draft(d: CopyDraft) -> dict:
    return {"id": str(d.id), "business_id": str(d.business_id) if d.business_id else None, "batch_id": d.batch_id,
            "kind": d.kind, "channel": d.channel, "industry": d.industry, "subject": d.subject, "body": d.body,
            "meta": d.meta, "source": d.source, "created_at": d.created_at.isoformat() if d.created_at else None}


@router.get("/status")
async def status():
    return {"llm_available": llm.available(), "provider": llm.provider_name(),
            "fallback": "template engine" if not llm.available() else None}


@router.get("/industries")
async def industries():
    return {"industries": [{"key": k, "label": v["label"], "pains": v["pains"], "offers": v["offers"]} for k, v in INDUSTRIES.items()],
            "content_types": [{"key": k, "label": v} for k, v in CONTENT_TYPES.items()]}


@router.post("/icebreakers")
async def icebreakers(body: IcebreakerIn, db: AsyncSession = Depends(get_db),
                      ctx: WorkspaceContext = Depends(require_permission("copy:generate"))):
    await enforce_limit(db, ctx.workspace.id, "ai_generations")
    b, audit = await _lead_and_audit(db, ctx, body.business_id)
    lead = _biz_to_dict(b) if b else (body.lead or {})
    if not lead:
        raise HTTPException(status_code=400, detail="Pick a lead or send lead details")
    res = await engine.icebreakers(lead, audit, max(1, min(body.count, 6)), body.tone)
    db.add(CopyDraft(workspace_id=ctx.workspace.id, business_id=b.id if b else None, kind="icebreaker",
                     industry=res["industry"], body="\n".join(res["icebreakers"]), source=res["source"],
                     meta={"icebreakers": res["icebreakers"]}))
    await db.commit()
    await record_usage(db, ctx.workspace.id, "ai_generations")
    return res


@router.post("/bulk")
async def bulk(body: BulkIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("copy:generate"))):
    ids = [uuid.UUID(i) for i in body.business_ids if i]
    if body.list_id:
        ids += list((await db.execute(select(LeadListItem.business_id).where(LeadListItem.list_id == uuid.UUID(body.list_id)))).scalars().all())
    if not ids:
        raise HTTPException(status_code=400, detail="Select leads or a list")
    leads = (await db.execute(select(SavedBusiness).where(SavedBusiness.id.in_(ids), lead_scope(ctx)).limit(200))).scalars().all()
    await enforce_limit(db, ctx.workspace.id, "ai_generations", amount=len(leads))
    sender = sender_for(ctx)
    batch = uuid.uuid4().hex[:12]
    sem = asyncio.Semaphore(4)

    async def one(b: SavedBusiness):
        async with sem:
            _, audit = await _lead_and_audit(db, ctx, str(b.id))
            lead = _biz_to_dict(b)
            opener = None
            if body.use_icebreaker:
                ib = await engine.icebreakers(lead, audit, 1)
                opener = ib["icebreakers"][0] if ib["icebreakers"] else None
            extra = body.instructions + (f" Open with this line: {opener}" if opener else "")
            return b, await engine.generate_email(lead, audit, sender, body.tone, body.channel, body.industry, extra)

    results = []
    for b, res in [await one(b) for b in leads]:  # sequential DB access on one session
        d = CopyDraft(workspace_id=ctx.workspace.id, business_id=b.id, batch_id=batch, kind="email", channel=body.channel,
                      industry=res["industry"], subject=res.get("subject"), body=res["body"], source=res["source"],
                      meta={"to": b.email, "business_name": b.business_name})
        db.add(d)
        await db.flush()
        results.append({**_draft(d), "business_name": b.business_name, "to": b.email})
    await db.commit()
    await record_usage(db, ctx.workspace.id, "ai_generations", len(results))
    return {"batch_id": batch, "count": len(results), "drafts": results}


@router.post("/reply")
async def reply(body: ReplyIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("copy:generate"))):
    await enforce_limit(db, ctx.workspace.id, "ai_generations")
    b, _ = await _lead_and_audit(db, ctx, body.business_id)
    res = await engine.reply_assistant(body.message, {"business_name": b.business_name} if b else {},
                                       sender_for(ctx), body.history, body.instruction)
    db.add(CopyDraft(workspace_id=ctx.workspace.id, business_id=b.id if b else None, kind="reply",
                     body=res["suggested_replies"][0]["body"] if res["suggested_replies"] else "", source=res["source"],
                     meta={"incoming": body.message[:2000], "intent": res["intent"], "replies": res["suggested_replies"]}))
    await db.commit()
    await record_usage(db, ctx.workspace.id, "ai_generations")
    return res


@router.post("/industry-content")
async def industry_content(body: IndustryIn, db: AsyncSession = Depends(get_db),
                           ctx: WorkspaceContext = Depends(require_permission("copy:generate"))):
    await enforce_limit(db, ctx.workspace.id, "ai_generations")
    b, _ = await _lead_and_audit(db, ctx, body.business_id)
    res = await engine.industry_content(body.industry, body.content_type, _biz_to_dict(b) if b else None,
                                        sender_for(ctx), body.tone)
    db.add(CopyDraft(workspace_id=ctx.workspace.id, business_id=b.id if b else None, kind="industry_content",
                     industry=body.industry, subject=res["title"], body=res["body"], source=res["source"],
                     meta={"content_type": body.content_type}))
    await db.commit()
    await record_usage(db, ctx.workspace.id, "ai_generations")
    return res


@router.get("/drafts")
async def drafts(batch_id: Optional[str] = None, kind: Optional[str] = None, db: AsyncSession = Depends(get_db),
                 ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    q = select(CopyDraft).where(CopyDraft.workspace_id == ctx.workspace.id)
    if batch_id:
        q = q.where(CopyDraft.batch_id == batch_id)
    if kind:
        q = q.where(CopyDraft.kind == kind)
    rows = (await db.execute(q.order_by(CopyDraft.created_at.desc()).limit(300))).scalars().all()
    return {"drafts": [_draft(d) for d in rows]}


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: str, body: DraftUpdate, db: AsyncSession = Depends(get_db),
                       ctx: WorkspaceContext = Depends(require_permission("copy:generate"))):
    d = ctx.ensure(await db.get(CopyDraft, uuid.UUID(draft_id)), "Draft")
    if body.subject is not None:
        d.subject = body.subject
    if body.body is not None:
        d.body = body.body
    await db.commit()
    return _draft(d)


@router.delete("/drafts/{draft_id}")
async def delete_draft(draft_id: str, db: AsyncSession = Depends(get_db),
                       ctx: WorkspaceContext = Depends(require_permission("copy:generate"))):
    d = ctx.ensure(await db.get(CopyDraft, uuid.UUID(draft_id)), "Draft")
    await db.delete(d)
    await db.commit()
    return {"message": "deleted"}

