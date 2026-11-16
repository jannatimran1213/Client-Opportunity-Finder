"""
Background jobs API (Celery + Redis). Long tasks - scraping, audits, bulk AI writing, bulk email /
WhatsApp sends, validation - are queued here so the UI stays responsive; the page polls GET /jobs/{id}.
"""
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenancy import WorkspaceContext, get_workspace_context, require_permission
from app.db.session import get_db
from app.models.job import BackgroundJob
from app.services.jobs.runner import JOB_KINDS, dispatch

router = APIRouter()

PERMS = {"finder_search": "leads:read", "scrape": "leads:read", "advanced_audit": "audits:run", "bulk_audit": "audits:run",
         "benchmark": "audits:run", "validate_leads": "leads:write", "bulk_copy": "copy:generate",
         "bulk_email_send": "outreach:send", "bulk_whatsapp": "outreach:send"}


class JobIn(BaseModel):
    kind: str
    payload: Dict[str, Any] = {}


def _job(j: BackgroundJob, full: bool = True) -> dict:
    d = {"id": str(j.id), "kind": j.kind, "label": JOB_KINDS.get(j.kind, j.kind), "status": j.status, "runner": j.runner,
         "error": j.error, "created_at": j.created_at.isoformat() if j.created_at else None,
         "started_at": j.started_at.isoformat() if j.started_at else None,
         "finished_at": j.finished_at.isoformat() if j.finished_at else None}
    if full:
        d["result"], d["payload"] = j.result, j.payload
    return d


@router.get("/kinds")
async def kinds():
    from app.core.celery_app import broker_available
    return {"kinds": JOB_KINDS, "celery_broker_available": broker_available()}


@router.post("")
async def create_job(body: JobIn, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    if body.kind not in JOB_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {list(JOB_KINDS)}")
    if not ctx.can(PERMS[body.kind]):
        raise HTTPException(status_code=403, detail=f"Your role cannot run '{body.kind}'")
    j = BackgroundJob(workspace_id=ctx.workspace.id, user_id=ctx.user.id, kind=body.kind, payload=body.payload, status="queued")
    db.add(j)
    await db.commit()
    await dispatch(db, j)
    return _job(j, full=False)


@router.get("")
async def list_jobs(db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    rows = (await db.execute(select(BackgroundJob).where(BackgroundJob.workspace_id == ctx.workspace.id)
                             .order_by(BackgroundJob.created_at.desc()).limit(50))).scalars().all()
    return {"jobs": [_job(j, full=False) for j in rows]}


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db), ctx: WorkspaceContext = Depends(get_workspace_context)):
    j = ctx.ensure(await db.get(BackgroundJob, uuid.UUID(job_id)), "Job")
    await db.refresh(j)
    return _job(j)

