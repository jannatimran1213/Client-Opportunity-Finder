"""
Module 2 - Custom Business Finder.

  POST /finder/search    Search by Type & City (OpenStreetMap / Overpass)  + optional auto website + scrape
  POST /finder/scrape    Proprietary Web Scraper (multi-page crawl of a site)
  POST /finder/parse     Data Parser & Extraction (emails / phones / WhatsApp / socials / schema.org)
  POST /finder/discover  Find Websites Automatically (search-engine discovery for leads without a site)
  POST /finder/save      Save results as leads (with duplicate check)
  GET  /finder/history   Previous searches
"""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenancy import WorkspaceContext, get_workspace_context, lead_scope, require_permission
from app.core.security import security_manager
from app.db.session import get_db
from app.models.saved_business import SavedBusiness
from app.models.search_job import SearchJob
from app.services.finder.parser import parse_content
from app.services.leads.dedupe import find_matches

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=6)


class SearchIn(BaseModel):
    business_type: str
    city: str
    country: str = ""
    radius_meters: int = Field(default=8000, ge=500, le=50000)
    auto_find_websites: bool = False
    scrape_contacts: bool = False
    max_results: int = Field(default=100, ge=1, le=500)


class ScrapeIn(BaseModel):
    url: str
    max_pages: int = Field(default=10, ge=1, le=30)


class ParseIn(BaseModel):
    url: Optional[str] = None
    html: Optional[str] = None
    text: Optional[str] = None


class DiscoverItem(BaseModel):
    business_name: str
    city: Optional[str] = ""
    country: Optional[str] = ""


class DiscoverIn(BaseModel):
    businesses: List[DiscoverItem]


class SaveIn(BaseModel):
    businesses: List[dict]
    list_id: Optional[str] = None
    skip_duplicates: bool = True


def _discover(name: str, city: str, country: str) -> Optional[str]:
    from app.services.osm.website_discovery import discover_website
    try:
        return discover_website(name, city or "", country or "")
    except Exception:
        return None


async def _scrape(url: str, max_pages: int = 10) -> dict:
    from app.services.scraping.website_scraper import scrape_website_for_contacts
    url = security_manager.normalize_url(url)
    contacts = await scrape_website_for_contacts(url, max_pages=max_pages)
    return contacts.to_dict() if contacts else {}


async def _existing_leads(db: AsyncSession, ctx: WorkspaceContext) -> List[dict]:
    rows = (await db.execute(select(SavedBusiness).where(lead_scope(ctx)))).scalars().all()
    return [{"id": str(b.id), "business_name": b.business_name, "website": b.website, "email": b.email,
             "phone": b.phone, "city": b.city} for b in rows]


@router.get("/business-types")
async def business_types():
    from app.services.osm.osm_service import OSMService
    return OSMService().get_business_types()


@router.post("/search")
async def search(body: SearchIn, db: AsyncSession = Depends(get_db),
                 ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    from app.services.osm.osm_service import OSMService
    loop = asyncio.get_event_loop()
    t0 = time.time()
    try:
        data = await loop.run_in_executor(executor, lambda: OSMService().search_businesses(
            business_type=security_manager.sanitize_text(body.business_type, 80),
            city=security_manager.sanitize_text(body.city, 80),
            country=security_manager.sanitize_text(body.country, 80),
            radius_meters=body.radius_meters))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Business search failed: {e}")
    print(f"[FINDER] 1) map search: {time.time() - t0:.1f}s")
    results = (data.get("results") or [])[: body.max_results]

    if body.auto_find_websites:
        t1 = time.time()
        missing = [r for r in results if not r.get("website")][:25]
        found = await asyncio.gather(*[loop.run_in_executor(executor, _discover, r.get("business_name"),
                                                            r.get("city") or body.city, body.country) for r in missing])
        for r, site in zip(missing, found):
            if site:
                r["website"] = site
                r["website_source"] = "auto-discovered"
        print(f"[FINDER] 2) finding websites for {len(missing)} businesses: {time.time() - t1:.1f}s")

    if body.scrape_contacts:
        t2 = time.time()
        targets = [r for r in results if r.get("website") and not r.get("email")][:15]
        scraped = await asyncio.gather(*[_scrape(r["website"], 5) for r in targets], return_exceptions=True)
        for r, s in zip(targets, scraped):
            if isinstance(s, dict):
                r["email"] = r.get("email") or s.get("best_email")
                r["phone"] = r.get("phone") or s.get("best_phone")
                for k in ("facebook", "instagram", "linkedin", "twitter"):
                    if s.get(k) and not r.get(k):
                        r[k] = s[k]
        print(f"[FINDER] 3) scraping {len(targets)} websites: {time.time() - t2:.1f}s")

    existing = await _existing_leads(db, ctx)
    for r in results:
        r["duplicates"] = find_matches(r, existing)
        r["already_saved"] = bool(r["duplicates"])

    job = SearchJob(workspace_id=ctx.workspace.id, user_id=ctx.user.id, kind="search", business_type=body.business_type,
                    city=body.city, country=body.country, result_count=len(results), results=results[:200])
    db.add(job)
    await db.commit()
    print(f"[FINDER] total: {time.time() - t0:.1f}s")
    return {"job_id": str(job.id), "query": data.get("query"), "result_count": len(results),
            "with_website": sum(1 for r in results if r.get("website")),
            "with_email": sum(1 for r in results if r.get("email")), "results": results}
@router.post("/scrape")
async def scrape(body: ScrapeIn, db: AsyncSession = Depends(get_db),
                 ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    url = security_manager.normalize_url(body.url)
    if not security_manager.is_safe_redirect_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL")
    try:
        contacts = await _scrape(url, body.max_pages)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e}")
    parsed = {}
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as c:
            r = await c.get(url)
        parsed = parse_content(r.text, str(r.url))
    except Exception:
        pass
    result = {"url": url, "contacts": contacts, "parsed": parsed}
    db.add(SearchJob(workspace_id=ctx.workspace.id, user_id=ctx.user.id, kind="scrape", target_url=url,
                     result_count=len(contacts.get("emails") or []), results=[result]))
    await db.commit()
    return result


@router.post("/parse")
async def parse(body: ParseIn, ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    content, base = body.html or body.text, None
    if not content and body.url:
        base = security_manager.normalize_url(body.url)
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as c:
                r = await c.get(base)
            content, base = r.text, str(r.url)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Could not fetch page: {e}")
    if not content:
        raise HTTPException(status_code=400, detail="Send url, html or text")
    return parse_content(content[:2_000_000], base or body.url)


@router.post("/discover")
async def discover(body: DiscoverIn, ctx: WorkspaceContext = Depends(require_permission("leads:read"))):
    loop = asyncio.get_event_loop()
    items = body.businesses[:30]
    found = await asyncio.gather(*[loop.run_in_executor(executor, _discover, b.business_name, b.city, b.country) for b in items])
    return {"results": [{"business_name": b.business_name, "city": b.city, "website": site, "found": bool(site)}
                        for b, site in zip(items, found)],
            "found_count": sum(1 for s in found if s)}


@router.post("/save")
async def save(body: SaveIn, db: AsyncSession = Depends(get_db),
               ctx: WorkspaceContext = Depends(require_permission("leads:write"))):
    from app.api.v1.endpoints.leads import save_leads
    return await save_leads(db, ctx, body.businesses, body.list_id, body.skip_duplicates)


@router.get("/history")
async def history(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    rows = (await db.execute(select(SearchJob).where(SearchJob.workspace_id == ctx.workspace.id)
                             .order_by(SearchJob.created_at.desc()).limit(50))).scalars().all()
    return {"jobs": [{"id": str(j.id), "kind": j.kind, "business_type": j.business_type, "city": j.city,
                      "country": j.country, "target_url": j.target_url, "result_count": j.result_count,
                      "created_at": j.created_at.isoformat() if j.created_at else None} for j in rows]}


@router.get("/history/{job_id}")
async def history_item(job_id: str, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    import uuid as _uuid
    job = ctx.ensure(await db.get(SearchJob, _uuid.UUID(job_id)), "Search")
    return {"id": str(job.id), "kind": job.kind, "results": job.results, "business_type": job.business_type,
            "city": job.city, "country": job.country}

