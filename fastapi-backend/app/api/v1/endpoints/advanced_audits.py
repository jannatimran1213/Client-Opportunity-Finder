"""
Module 4 - Advanced Audit endpoints.

  POST /advanced-audits/run         Speed & Security + Tech Stack + Mobile Friendliness for one URL
  POST /advanced-audits/benchmark   Competitor Benchmarking (given URLs, or auto-found by category + city)
  GET  /advanced-audits             History;  GET /advanced-audits/{id}
"""
import asyncio
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenancy import WorkspaceContext, get_workspace_context, lead_scope, require_permission
from app.core.security import security_manager
from app.db.session import get_db
from app.models.advanced_audit import AdvancedAudit, CompetitorBenchmark
from app.models.saved_business import SavedBusiness
from app.services.billing.plans import enforce_limit, record_usage
from app.services.website_audit.advanced import benchmark, run_advanced_audit

router = APIRouter()


class RunIn(BaseModel):
    url: Optional[str] = None
    business_id: Optional[str] = None


class BenchmarkIn(BaseModel):
    target_url: str
    competitor_urls: List[str] = []
    auto_find: bool = False
    category: Optional[str] = None
    city: Optional[str] = None


def _row(a: AdvancedAudit, full: bool = False) -> dict:
    d = {"id": str(a.id), "url": a.url, "business_id": str(a.business_id) if a.business_id else None,
         "overall_score": a.overall_score, "speed_score": a.speed_score, "security_score": a.security_score,
         "mobile_score": a.mobile_score, "seo_score": a.seo_score, "trust_score": a.trust_score,
         "leak_count": a.leak_count, "tech_stack": a.tech_stack,
         "created_at": a.created_at.isoformat() if a.created_at else None}
    if full:
        d["report"] = a.report
    return d


def find_competitors(category: str, city: str, exclude_domain: str = "", limit: int = 4) -> List[str]:
    from ddgs import DDGS
    from app.services.osm.website_discovery import _get_base_url, _is_skip_domain
    urls: List[str] = []
    try:
        with DDGS() as d:
            for r in d.text(f"best {category} in {city}", max_results=20):
                u = r.get("href", "")
                if not u or _is_skip_domain(u) or (exclude_domain and exclude_domain in u):
                    continue
                base = _get_base_url(u)
                if base not in urls:
                    urls.append(base)
                if len(urls) >= limit:
                    break
    except Exception:
        pass
    return urls


@router.post("/run")
async def run(body: RunIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("audits:run"))):
    biz = None
    url = body.url
    if body.business_id:
        biz = (await db.execute(select(SavedBusiness).where(SavedBusiness.id == uuid.UUID(body.business_id), lead_scope(ctx)))).scalars().first()
        if not biz:
            raise HTTPException(status_code=404, detail="Lead not found")
        url = url or biz.website
    if not url:
        raise HTTPException(status_code=400, detail="A URL (or a lead with a website) is required")
    await enforce_limit(db, ctx.workspace.id, "audits")
    report = await run_advanced_audit(security_manager.normalize_url(url))
    if report.get("error"):
        raise HTTPException(status_code=502, detail=report["error"])
    a = AdvancedAudit(workspace_id=ctx.workspace.id, business_id=biz.id if biz else None, url=report["url"],
                      overall_score=report["overall_score"], speed_score=report["speed"]["score"],
                      security_score=report["security"]["score"], mobile_score=report["mobile"]["score"],
                      seo_score=report["seo"]["score"], trust_score=report["trust"]["score"], leak_count=report["trust"]["leak_count"],
                      tech_stack=report["tech_stack"], report=report)
    db.add(a)
    if biz:
        biz.audit_completed = True
        biz.overall_score = report["overall_score"]
        biz.load_speed_score = report["speed"]["score"]
        biz.ssl_score = report["security"]["score"]
        biz.responsiveness_score = report["mobile"]["score"]
        biz.seo_score = report["seo"]["score"]
        biz.audit_summary = "; ".join(report.get("opportunities") or [])[:2000]
    await db.commit()
    await record_usage(db, ctx.workspace.id, "audits")
    return {"id": str(a.id), **report}


@router.post("/leaks")
async def leaks_only(body: RunIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("audits:run"))):
    """Trust & Conversion Leak Detector as a standalone check (runs the same audit, returns the leak report)."""
    res = await run(body, db, ctx)
    return {"id": res["id"], "url": res["url"], "trust": res["trust"], "seo": res["seo"], "opportunities": res["opportunities"]}


@router.get("")
async def history(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    rows = (await db.execute(select(AdvancedAudit).where(AdvancedAudit.workspace_id == ctx.workspace.id)
                             .order_by(AdvancedAudit.created_at.desc()).limit(100))).scalars().all()
    return {"audits": [_row(a) for a in rows]}


@router.post("/benchmark")
async def run_benchmark(body: BenchmarkIn, db: AsyncSession = Depends(get_db),
                        ctx: WorkspaceContext = Depends(require_permission("audits:run"))):
    from urllib.parse import urlparse
    target = security_manager.normalize_url(body.target_url)
    comps = [security_manager.normalize_url(u) for u in body.competitor_urls if u.strip()]
    if body.auto_find and len(comps) < 3:
        if not (body.category and body.city):
            raise HTTPException(status_code=400, detail="Auto-find needs category and city")
        loop = asyncio.get_event_loop()
        found = await loop.run_in_executor(None, find_competitors, body.category, body.city,
                                           urlparse(target).netloc.replace("www.", ""))
        comps += [u for u in found if u not in comps]
    if not comps:
        raise HTTPException(status_code=400, detail="Add at least one competitor URL (or use auto-find)")
    await enforce_limit(db, ctx.workspace.id, "audits", amount=1 + len(comps[:5]))
    result = await benchmark(target, comps[:5])
    bm = CompetitorBenchmark(workspace_id=ctx.workspace.id, target_url=target, competitor_urls=comps[:5],
                             ranking=result["ranking"], insights=result["insights"])
    db.add(bm)
    await db.commit()
    await record_usage(db, ctx.workspace.id, "audits", 1 + len(comps[:5]))
    return {"id": str(bm.id), **result}


@router.get("/benchmarks")
async def benchmarks(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    rows = (await db.execute(select(CompetitorBenchmark).where(CompetitorBenchmark.workspace_id == ctx.workspace.id)
                             .order_by(CompetitorBenchmark.created_at.desc()).limit(50))).scalars().all()
    return {"benchmarks": [{"id": str(b.id), "target_url": b.target_url, "competitor_urls": b.competitor_urls,
                            "ranking": b.ranking, "insights": b.insights,
                            "created_at": b.created_at.isoformat() if b.created_at else None} for b in rows]}


@router.get("/{audit_id}")
async def get_one(audit_id: str, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    a = ctx.ensure(await db.get(AdvancedAudit, uuid.UUID(audit_id)), "Audit")
    return _row(a, full=True)


@router.delete("/{audit_id}")
async def delete_one(audit_id: str, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(require_permission("audits:run"))):
    a = ctx.ensure(await db.get(AdvancedAudit, uuid.UUID(audit_id)), "Audit")
    await db.delete(a)
    await db.commit()
    return {"message": "deleted"}

