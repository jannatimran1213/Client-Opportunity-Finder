"""Celery entry point:  celery -A workers.celery_worker worker --loglevel=info"""
from app.core.celery_app import celery_app  # noqa: F401
import app.models  # noqa: F401  (register all SQLAlchemy models)

app = celery_app
