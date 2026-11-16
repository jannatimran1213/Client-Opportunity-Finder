"""
Background job runner shared by Celery workers and the in-process fallback.

dispatch(job) -> sends the job to Celery when Redis + a worker are available, otherwise schedules
it on the API's own event loop. Either way run_job() executes the same module code and stores
status / progress / result on the background_jobs row the UI polls.
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import select

from app.core.config import settings

logger = logging.getLogger(__name__)
_workers = {"checked": 0.0, "count": 0}

JOB_KINDS = {
    "finder_search": "Search businesses by type & city (+ website discovery / scraping)",
    "scrape": "Crawl one website for contacts",
    "advanced_audit": "Advanced audit of one URL / lead",
    "bulk_audit": "Advanced audit of many leads",
    "benchmark": "Competitor benchmark",
    "validate_leads": "Validate emails / phones / websites",
    "bulk_copy": "Generate AI emails for many leads",
    "bulk_email_send": "Send a batch of drafts (tracked)",
    "bulk_whatsapp": "Send WhatsApp messages to many leads",
}


async def _context(db, job):
    from app.api.tenancy import WorkspaceContext
    from app.models.user import User
    from app.models.workspace import Workspace, WorkspaceMember
    ws = await db.get(Workspace, job.workspace_id)
    user = await db.get(User, job.user_id)
    member = (await db.execute(select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id,
                                                             WorkspaceMember.user_id == user.id))).scalars().first()
    return WorkspaceContext(user, ws, member.role if member else ("owner" if user.role == "admin" else "viewer"))


async def _execute(kind: str, payload: Dict[str, Any], db, ctx) -> Dict[str, Any]:
    from app.api.v1.endpoints import advanced_audits, channels, copywriter, finder, leads
    if kind == "finder_search":
        return await finder.search(finder.SearchIn(**payload), db, ctx)
    if kind == "scrape":
        return await finder.scrape(finder.ScrapeIn(**payload), db, ctx)
    if kind == "advanced_audit":
        return await advanced_audits.run(advanced_audits.RunIn(**payload), db, ctx)
    if kind == "bulk_audit":
        done, failed = [], []
        for bid in payload.get("business_ids", [])[:200]:
            try:
                r = await advanced_audits.run(advanced_audits.RunIn(business_id=bid), db, ctx)
                done.append({"business_id": bid, "overall_score": r["overall_score"]})
            except Exception as e:
                failed.append({"business_id": bid, "error": getattr(e, "detail", str(e))})
        return {"audited": len(done), "failed": len(failed), "results": done, "errors": failed}
    if kind == "benchmark":
        return await advanced_audits.run_benchmark(advanced_audits.BenchmarkIn(**payload), db, ctx)
    if kind == "validate_leads":
        return await leads.validate(leads.ValidateIn(**payload), db, ctx)
    if kind == "bulk_copy":
        return await copywriter.bulk(copywriter.BulkIn(**payload), db, ctx)
    if kind == "bulk_email_send":
        return await channels.email_send_batch(channels.BatchSendIn(**payload), db, ctx)
    if kind == "bulk_whatsapp":
        sent, errors = 0, []
        for bid in payload.get("business_ids", [])[:500]:
            try:
                await channels.whatsapp_send(channels.WhatsAppIn(business_id=bid, body=payload.get("body", ""),
                                                                 template_name=payload.get("template_name")), db, ctx)
                sent += 1
            except Exception as e:
                errors.append({"business_id": bid, "error": getattr(e, "detail", str(e))})
            await asyncio.sleep(float(payload.get("delay_seconds", 1)))
        return {"sent": sent, "failed": len(errors), "errors": errors}
    raise ValueError(f"Unknown job kind {kind}")


def _jsonable(obj):
    import json
    return json.loads(json.dumps(obj, default=str))


async def run_job(job_id: str, fresh_engine: bool = False) -> None:
    """Execute a job. fresh_engine=True is used inside Celery workers (each task has its own event loop)."""
    from app.models.job import BackgroundJob
    if fresh_engine:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        Session = async_sessionmaker(engine, expire_on_commit=False)
    else:
        from app.db.session import AsyncSessionLocal as Session
        engine = None
    try:
        async with Session() as db:
            job = await db.get(BackgroundJob, uuid.UUID(str(job_id)))
            if not job:
                return
            job.status, job.started_at = "running", datetime.now(timezone.utc)
            await db.commit()
            try:
                ctx = await _context(db, job)
                result = await _execute(job.kind, job.payload or {}, db, ctx)
                job.result, job.status = _jsonable(result), "completed"
            except Exception as e:
                logger.exception("job %s failed", job_id)
                await db.rollback()
                job = await db.get(BackgroundJob, uuid.UUID(str(job_id)))
                job.status, job.error = "failed", str(getattr(e, "detail", e))[:2000]
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
    finally:
        if engine is not None:
            await engine.dispose()


_background: set = set()


def _celery_ready() -> bool:
    from app.core.celery_app import broker_available, workers_online
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return False  # eager mode would block the request; the in-process path is equivalent and async
    if not broker_available():
        return False
    now = time.time()
    if now - _workers["checked"] > 30:
        _workers.update(checked=now, count=workers_online())
    return _workers["count"] > 0


async def dispatch(db, job) -> str:
    loop = asyncio.get_event_loop()
    use_celery = await loop.run_in_executor(None, _celery_ready)
    if use_celery:
        from workers.tasks.jobs import run_background_job
        res = run_background_job.delay(str(job.id))
        job.runner, job.celery_task_id = "celery", res.id
    else:
        job.runner = "in-process"
        task = asyncio.create_task(run_job(str(job.id)))
        _background.add(task)
        task.add_done_callback(_background.discard)
    await db.commit()
    return job.runner

