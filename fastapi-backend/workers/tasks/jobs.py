import asyncio

from app.core.celery_app import celery_app


@celery_app.task(name="workers.tasks.jobs.run_background_job", bind=True, max_retries=0)
def run_background_job(self, job_id: str):
    """Generic job: finder search, scraping, audits, bulk AI, bulk email/WhatsApp, validation."""
    from app.services.jobs.runner import run_job
    asyncio.run(run_job(job_id, fresh_engine=True))
    return {"job_id": job_id}
