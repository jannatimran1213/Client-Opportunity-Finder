"""Celery task: periodic inbox sync placeholder hook (the inbox sync itself lives in /api/v1/mail/sync)."""
from app.core.celery_app import celery_app


@celery_app.task(name="workers.tasks.imap_sync.ping")
def ping() -> str:
    return "pong"
