"""Celery task: advanced website audit (speed, security, tech stack, mobile, indexing, trust leaks) for a URL."""
import asyncio

from app.core.celery_app import celery_app


@celery_app.task(name="workers.tasks.run_audit.advanced_audit_url")
def advanced_audit_url(url: str) -> dict:
    from app.services.website_audit.advanced import run_advanced_audit
    return asyncio.run(run_advanced_audit(url))
