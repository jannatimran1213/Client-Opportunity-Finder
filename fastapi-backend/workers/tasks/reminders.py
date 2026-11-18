"""Celery beat tasks: deliver due meeting/follow-up reminders and run the smart no-reply check."""
import asyncio

from app.core.celery_app import celery_app


def _run(coro_factory):
    async def main():
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool
        from app.core.config import settings
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        try:
            return await coro_factory(async_sessionmaker(engine, expire_on_commit=False))
        finally:
            await engine.dispose()
    return asyncio.run(main())


@celery_app.task(name="workers.tasks.reminders.deliver_due_reminders")
def deliver_due_reminders() -> int:
    from app.services.meetings.reminders import process_due_reminders
    return _run(lambda Session: process_due_reminders(session_factory=Session))


@celery_app.task(name="workers.tasks.reminders.no_reply_check")
def no_reply_check() -> int:
    from app.services.meetings.reminders import detect_no_reply
    return _run(lambda Session: detect_no_reply(session_factory=Session))
