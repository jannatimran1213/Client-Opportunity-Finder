"""
Module 3 - Lead Management.

  Save Promising Businesses ... POST /leads/save, POST /finder/save
  Edit and Organize Lists ..... GET/PUT /leads, /leads/bulk, /leads/lists (+ items)
  Validation Filter ........... POST /leads/validate, GET /leads?email_status=valid
  Lead Duplication Check ...... GET /leads/duplicates, POST /leads/duplicates/merge, POST /leads/check-duplicate
"""
import csv
import io
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenancy import WorkspaceContext, get_workspace_context, lead_scope, require_permission
from app.api.v1.endpoints.businesses import _biz_to_dict
from app.core.security import security_manager
from app.db.session import get_db
from app.models.lead_list import LeadList, LeadListItem, LeadProfile
from app.models.saved_business import SavedBusiness
from app.services.billing.plans import enforce_limit
from app.services.leads.dedupe import find_duplicate_groups, find_matches
from app.services.leads.validation import validate_lead

router = APIRouter()

EDITABLE_FIELDS = ["business_name", "website", "email", "phone", "address", "city", "country", "category",
                   "notes", "facebook", "instagram"]
PROFILE_FIELDS = ["status", "priority", "tags", "linkedin_url", "whatsapp_number"]
STATUSES = ["new", "contacted", "replied", "meeting", "won", "lost"]


class LeadUpdate(BaseModel):
    business_name: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[List[str]] = None
    linkedin_url: Optional[str] = None
    whatsapp_number: Optional[str] = None


class BulkIn(BaseModel):
    ids: List[str]
    action: str  # set_status | add_tag | remove_tag | delete | add_to_list | remove_from_list | set_priority
    value: Optional[str] = None


class ListIn(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#6D5DF6"


class ItemsIn(BaseModel):
    business_ids: List[str]


class ValidateIn(BaseModel):
    ids: Optional[List[str]] = None
    all: bool = False
    check_website: bool = True
    check_mx: bool = True


class MergeIn(BaseModel):
    keep_id: str
    merge_ids: List[str]


class SaveIn(BaseModel):
    businesses: List[dict]
    list_id: Optional[str] = None
    skip_duplicates: bool = True


def _uuids(ids: List[str]) -> List[uuid.UUID]:
    out = []
    for i in ids:
        try:
            out.append(uuid.UUID(str(i)))
        except ValueError:
            continue
    return out


async def _profile(db: AsyncSession, ctx: WorkspaceContext, business_id: uuid.UUID) -> LeadProfile:
    p = await db.get(LeadProfile, business_id)
    if not p:
        p = LeadProfile(business_id=business_id, workspace_id=ctx.workspace.id, status="new", priority="medium", tags=[])
        db.add(p)
        await db.flush()
    return p


def _profile_dict(p: Optional[LeadProfile]) -> dict:
    if not p:
        return {"status": "new", "priority": "medium", "tags": [], "email_status": None, "phone_status": None,
                "website_status": None, "validation_score": None, "linkedin_url": None, "whatsapp_number": None}
    return {"status": p.status, "priority": p.priority, "tags": p.tags or [], "linkedin_url": p.linkedin_url,
            "whatsapp_number": p.whatsapp_number, "email_status": p.email_status, "email_reason": p.email_reason,
            "phone_status": p.phone_status, "phone_e164": p.phone_e164, "website_status": p.website_status,
            "website_http_code": p.website_http_code, "validation_score": p.validation_score,
            "validated_at": p.validated_at.isoformat() if p.validated_at else None}


async def _get_lead(db: AsyncSession, ctx: WorkspaceContext, lead_id: str) -> SavedBusiness:
    try:
        lid = uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Lead not found")
    b = (await db.execute(select(SavedBusiness).where(SavedBusiness.id == lid, lead_scope(ctx)))).scalars().first()
    if not b:
        raise HTTPException(status_code=404, detail="Lead not found")
    return b


async def save_leads(db: AsyncSession, ctx: WorkspaceContext, businesses: List[dict],
                     list_id: Optional[str] = None, skip_duplicates: bool = True) -> dict:
    """Shared by /leads/save and /finder/save: saves promising businesses with duplicate protection."""
    existing_rows = (await db.execute(select(SavedBusiness).where(lead_scope(ctx)))).scalars().all()
    existing = [_biz_to_dict(b) for b in existing_rows]
    await enforce_limit(db, ctx.workspace.id, "leads", amount=len(businesses), current=len(existing))
    target_list = None
    if list_id:
        target_list = ctx.ensure(await db.get(LeadList, uuid.UUID(list_id)), "List")

    saved, skipped, new_ids = 0, [], []
    for biz in businesses:
        name = biz.get("business_name") or biz.get("name") or biz.get("display_name")
        if not name:
            continue
        candidate = {**biz, "business_name": name}
        matches = find_matches(candidate, existing)
        if matches and skip_duplicates:
            skipped.append({"business_name": name, "duplicate_of": matches[0]})
            if target_list and matches[0].get("id"):
                new_ids.append(uuid.UUID(matches[0]["id"]))
            continue
        b = SavedBusiness(
            user_id=ctx.user.id, workspace_id=ctx.workspace.id,
            business_name=security_manager.sanitize_text(name, 255),
            website=biz.get("website"), email=biz.get("email"), phone=biz.get("phone"),
            address=biz.get("address"), city=biz.get("city"), country=biz.get("country"),
            category=biz.get("category") or biz.get("business_type"), notes=biz.get("notes"),
            facebook=biz.get("facebook"), instagram=biz.get("instagram"), lat=biz.get("lat"), lon=biz.get("lon"),
        )
        db.add(b)
        await db.flush()
        db.add(LeadProfile(business_id=b.id, workspace_id=ctx.workspace.id, status="new", priority="medium",
                           tags=[], linkedin_url=biz.get("linkedin")))
        existing.append({**candidate, "id": str(b.id)})
        new_ids.append(b.id)
        saved += 1
    if target_list:
        have = set((await db.execute(select(LeadListItem.business_id).where(LeadListItem.list_id == target_list.id))).scalars().all())
        for bid in new_ids:
            if bid not in have:
                db.add(LeadListItem(list_id=target_list.id, business_id=bid))
                have.add(bid)
    await db.commit()
    return {"saved": saved, "skipped_duplicates": len(skipped), "duplicates": skipped,
            "message": f"Saved {saved} leads, skipped {len(skipped)} duplicates"}


# â”€â”€ Leads â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("")
async def list_leads(
    list_id: Optional[str] = None, status: Optional[str] = None, tag: Optional[str] = None,
    email_status: Optional[str] = None, q: Optional[str] = None, has_email: Optional[bool] = None,
    page: int = Query(1, ge=1), per_page: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read")),
):
    query = select(SavedBusiness, LeadProfile).outerjoin(LeadProfile, LeadProfile.business_id == SavedBusiness.id).where(lead_scope(ctx))
    if list_id:
        query = query.join(LeadListItem, LeadListItem.business_id == SavedBusiness.id).where(LeadListItem.list_id == uuid.UUID(list_id))
    if status:
        query = query.where(LeadProfile.status == status) if status != "new" else query.where(
            (LeadProfile.status == "new") | (LeadProfile.status.is_(None)))
    if email_status:
        query = query.where(LeadProfile.email_status == email_status)
    if has_email is not None:
        query = query.where(SavedBusiness.email.isnot(None) if has_email else SavedBusiness.email.is_(None))
    if q:
        like = f"%{q}%"
        query = query.where(SavedBusiness.business_name.ilike(like) | SavedBusiness.city.ilike(like) |
                            SavedBusiness.category.ilike(like) | SavedBusiness.email.ilike(like))
    rows = (await db.execute(query.order_by(SavedBusiness.created_at.desc()))).all()
    if tag:
        rows = [r for r in rows if r[1] and tag in (r[1].tags or [])]
    total = len(rows)
    rows = rows[(page - 1) * per_page: page * per_page]
    ids = [b.id for b, _ in rows]
    memberships = {}
    if ids:
        for item in (await db.execute(select(LeadListItem).where(LeadListItem.business_id.in_(ids)))).scalars().all():
            memberships.setdefault(item.business_id, []).append(str(item.list_id))
    return {"total": total, "page": page, "per_page": per_page,
            "leads": [{**_biz_to_dict(b), **_profile_dict(p), "list_ids": memberships.get(b.id, [])} for b, p in rows]}


@router.post("/save")
async def save(body: SaveIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:write"))):
    return await save_leads(db, ctx, body.businesses, body.list_id, body.skip_duplicates)


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    rows = (await db.execute(select(SavedBusiness, LeadProfile).outerjoin(
        LeadProfile, LeadProfile.business_id == SavedBusiness.id).where(lead_scope(ctx)))).all()
    by_status = {s: 0 for s in STATUSES}
    by_email = {}
    for b, p in rows:
        by_status[(p.status if p else "new") or "new"] = by_status.get((p.status if p else "new") or "new", 0) + 1
        es = (p.email_status if p else None) or "unchecked"
        by_email[es] = by_email.get(es, 0) + 1
    return {"total": len(rows), "by_status": by_status, "by_email_status": by_email,
            "with_email": sum(1 for b, _ in rows if b.email), "with_website": sum(1 for b, _ in rows if b.website)}


@router.get("/export.csv")
async def export_csv(list_id: Optional[str] = None, db: AsyncSession = Depends(get_db),
                     ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    data = await list_leads(list_id=list_id, status=None, tag=None, email_status=None, q=None, has_email=None,
                            page=1, per_page=1000, db=db, ctx=ctx)
    buf = io.StringIO()
    cols = ["business_name", "category", "email", "email_status", "phone", "phone_e164", "website", "website_status",
            "city", "country", "status", "priority", "tags", "overall_score"]
    wr = csv.writer(buf)
    wr.writerow(cols)
    for lead in data["leads"]:
        wr.writerow([";".join(lead.get(c) or []) if c == "tags" else lead.get(c) for c in cols])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=leads.csv"})


@router.put("/{lead_id}")
async def update_lead(lead_id: str, body: LeadUpdate, db: AsyncSession = Depends(get_db),
                      ctx: WorkspaceContext = Depends(require_permission("leads:write"))):
    b = await _get_lead(db, ctx, lead_id)
    data = body.model_dump(exclude_unset=True)
    for k in EDITABLE_FIELDS:
        if k in data:
            setattr(b, k, security_manager.sanitize_text(data[k], 2000) if isinstance(data[k], str) else data[k])
    p = await _profile(db, ctx, b.id)
    for k in PROFILE_FIELDS:
        if k in data:
            if k == "status" and data[k] not in STATUSES:
                raise HTTPException(status_code=400, detail=f"status must be one of {STATUSES}")
            setattr(p, k, data[k])
    if b.workspace_id is None:
        b.workspace_id = ctx.workspace.id
    await db.commit()
    return {**_biz_to_dict(b), **_profile_dict(p)}


@router.post("/bulk")
async def bulk(body: BulkIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:write"))):
    ids = _uuids(body.ids)
    leads = (await db.execute(select(SavedBusiness).where(SavedBusiness.id.in_(ids), lead_scope(ctx)))).scalars().all()
    if body.action == "delete":
        if not ctx.can("leads:delete"):
            raise HTTPException(status_code=403, detail="Only owners/admins can delete leads")
        for b in leads:
            await db.delete(b)
        await db.commit()
        return {"updated": len(leads)}
    target = None
    if body.action in ("add_to_list", "remove_from_list"):
        target = ctx.ensure(await db.get(LeadList, uuid.UUID(body.value)), "List")
    for b in leads:
        p = await _profile(db, ctx, b.id)
        if body.action == "set_status" and body.value in STATUSES:
            p.status = body.value
        elif body.action == "set_priority":
            p.priority = body.value
        elif body.action == "add_tag" and body.value:
            p.tags = sorted(set((p.tags or []) + [body.value.strip()]))
        elif body.action == "remove_tag":
            p.tags = [t for t in (p.tags or []) if t != body.value]
        elif body.action == "add_to_list":
            exists = (await db.execute(select(LeadListItem).where(LeadListItem.list_id == target.id,
                                                                  LeadListItem.business_id == b.id))).scalars().first()
            if not exists:
                db.add(LeadListItem(list_id=target.id, business_id=b.id))
        elif body.action == "remove_from_list":
            await db.execute(delete(LeadListItem).where(LeadListItem.list_id == target.id, LeadListItem.business_id == b.id))
    await db.commit()
    return {"updated": len(leads)}


# â”€â”€ Lists â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/lists")
async def lists(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    rows = (await db.execute(select(LeadList).where(LeadList.workspace_id == ctx.workspace.id).order_by(LeadList.created_at))).scalars().all()
    counts = dict((await db.execute(select(LeadListItem.list_id, func.count()).group_by(LeadListItem.list_id))).all())
    return {"lists": [{"id": str(l.id), "name": l.name, "description": l.description, "color": l.color,
                       "count": counts.get(l.id, 0)} for l in rows]}


@router.post("/lists")
async def create_list(body: ListIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:write"))):
    l = LeadList(workspace_id=ctx.workspace.id, name=security_manager.sanitize_text(body.name, 120),
                 description=body.description, color=body.color or "#6D5DF6")
    db.add(l)
    await db.commit()
    return {"id": str(l.id), "name": l.name, "description": l.description, "color": l.color, "count": 0}


@router.put("/lists/{list_id}")
async def update_list(list_id: str, body: ListIn, db: AsyncSession = Depends(get_db),
                      ctx: WorkspaceContext = Depends(require_permission("leads:write"))):
    l = ctx.ensure(await db.get(LeadList, uuid.UUID(list_id)), "List")
    l.name, l.description, l.color = body.name, body.description, body.color or l.color
    await db.commit()
    return {"id": str(l.id), "name": l.name, "description": l.description, "color": l.color}


@router.delete("/lists/{list_id}")
async def delete_list(list_id: str, db: AsyncSession = Depends(get_db),
                      ctx: WorkspaceContext = Depends(require_permission("leads:write"))):
    l = ctx.ensure(await db.get(LeadList, uuid.UUID(list_id)), "List")
    await db.delete(l)
    await db.commit()
    return {"message": "List deleted (leads kept)"}


@router.post("/lists/{list_id}/items")
async def add_items(list_id: str, body: ItemsIn, db: AsyncSession = Depends(get_db),
                    ctx: WorkspaceContext = Depends(require_permission("leads:write"))):
    return await bulk(BulkIn(ids=body.business_ids, action="add_to_list", value=list_id), db, ctx)


@router.delete("/lists/{list_id}/items")
async def remove_items(list_id: str, body: ItemsIn, db: AsyncSession = Depends(get_db),
                       ctx: WorkspaceContext = Depends(require_permission("leads:write"))):
    return await bulk(BulkIn(ids=body.business_ids, action="remove_from_list", value=list_id), db, ctx)


# â”€â”€ Validation filter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/validate")
async def validate(body: ValidateIn, db: AsyncSession = Depends(get_db),
                   ctx: WorkspaceContext = Depends(require_permission("leads:write"))):
    import asyncio
    query = select(SavedBusiness).where(lead_scope(ctx))
    if not body.all:
        query = query.where(SavedBusiness.id.in_(_uuids(body.ids or [])))
    leads = (await db.execute(query.limit(300))).scalars().all()
    sem = asyncio.Semaphore(10)

    async def run(b):
        async with sem:
            return b, await validate_lead(_biz_to_dict(b), body.check_website, body.check_mx)

    results = await asyncio.gather(*[run(b) for b in leads])
    out = []
    for b, res in results:
        p = await _profile(db, ctx, b.id)
        p.email_status, p.email_reason = res["email"]["status"], res["email"].get("reason")
        p.phone_status, p.phone_e164 = res["phone"]["status"], res["phone"].get("e164")
        if res["website"]["status"] != "skipped":
            p.website_status, p.website_http_code = res["website"]["status"], res["website"].get("http_code")
        p.validation_score = res["score"]
        p.validated_at = datetime.now(timezone.utc)
        out.append({"id": str(b.id), "business_name": b.business_name, **res})
    await db.commit()
    summary = {
        "checked": len(out),
        "valid_emails": sum(1 for r in out if r["email"]["status"] == "valid"),
        "invalid_emails": sum(1 for r in out if r["email"]["status"] == "invalid"),
        "valid_phones": sum(1 for r in out if r["phone"]["status"] == "valid"),
        "reachable_websites": sum(1 for r in out if r["website"]["status"] == "reachable"),
    }
    return {"summary": summary, "results": out}


# â”€â”€ Duplicate check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/duplicates")
async def duplicates(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    rows = (await db.execute(select(SavedBusiness).where(lead_scope(ctx)))).scalars().all()
    groups = find_duplicate_groups([_biz_to_dict(b) for b in rows])
    return {"group_count": len(groups), "duplicate_leads": sum(len(g["leads"]) - 1 for g in groups), "groups": groups}


@router.post("/check-duplicate")
async def check_duplicate(body: dict, db: AsyncSession = Depends(get_db),
                          ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    rows = (await db.execute(select(SavedBusiness).where(lead_scope(ctx)))).scalars().all()
    matches = find_matches(body, [_biz_to_dict(b) for b in rows])
    return {"is_duplicate": bool(matches), "matches": matches}


@router.post("/duplicates/merge")
async def merge(body: MergeIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:write"))):
    keep = await _get_lead(db, ctx, body.keep_id)
    others = (await db.execute(select(SavedBusiness).where(SavedBusiness.id.in_(_uuids(body.merge_ids)), lead_scope(ctx),
                                                           SavedBusiness.id != keep.id))).scalars().all()
    for o in others:
        for f in EDITABLE_FIELDS + ["lat", "lon", "overall_score", "audit_summary"]:
            if not getattr(keep, f, None) and getattr(o, f, None):
                setattr(keep, f, getattr(o, f))
        if o.notes and keep.notes and o.notes not in keep.notes:
            keep.notes = f"{keep.notes}\n{o.notes}"
        # move list memberships to the kept lead
        for item in (await db.execute(select(LeadListItem).where(LeadListItem.business_id == o.id))).scalars().all():
            dup = (await db.execute(select(LeadListItem).where(LeadListItem.list_id == item.list_id,
                                                               LeadListItem.business_id == keep.id))).scalars().first()
            if dup:
                await db.delete(item)
            else:
                item.business_id = keep.id
        await db.flush()
        await db.delete(o)
    await db.commit()
    return {"kept": str(keep.id), "merged": len(others)}

