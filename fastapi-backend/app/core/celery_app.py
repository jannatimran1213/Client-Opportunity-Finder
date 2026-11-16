"""
Celery application (Celery 5.3+, Redis broker/result backend at REDIS_URL).

Start the workers:
    celery -A workers.celery_worker worker --loglevel=info          # background jobs
    celery -A workers.celery_worker beat --loglevel=info            # reminders + no-reply checks every minute

If Redis is not reachable (or CELERY_ENABLED=false) the API runs the same jobs in-process, so
local development works without Redis.
"""
import time

from celery import Celery

from app.core.config import settings

celery_app = Celery("orbiscout", broker=settings.REDIS_URL, backend=settings.REDIS_URL,
                    include=["workers.tasks.run_audit", "workers.tasks.ingest_osm", "workers.tasks.smtp_send",
                             "workers.tasks.ai_generate_email", "workers.tasks.imap_sync", "workers.tasks.reminders",
                             "workers.tasks.jobs"])
celery_app.conf.update(
    task_serializer="json", accept_content=["json"], result_serializer="json", timezone="UTC", enable_utc=True,
    task_acks_late=True, worker_prefetch_multiplier=1, task_time_limit=60 * 30, broker_connection_retry_on_startup=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    beat_schedule={
        "deliver-due-reminders": {"task": "workers.tasks.reminders.deliver_due_reminders", "schedule": 60.0},
        "smart-no-reply-check": {"task": "workers.tasks.reminders.no_reply_check", "schedule": 900.0},
    },
)

_status = {"checked": 0.0, "ok": False}


def broker_available(cache_seconds: int = 30) -> bool:
    """True when Celery is enabled and the Redis broker answers (cached)."""
    if not settings.CELERY_ENABLED:
        return False
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return True
    now = time.time()
    if now - _status["checked"] < cache_seconds:
        return _status["ok"]
    try:
        import redis
        redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1).ping()
        ok = True
    except Exception:
        ok = False
    _status.update(checked=now, ok=ok)
    return ok


def workers_online(timeout: float = 1.0) -> int:
    try:
        replies = celery_app.control.ping(timeout=timeout)
        return len(replies or [])
    except Exception:
        return 0

