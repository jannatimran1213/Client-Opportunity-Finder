"""Celery beat:  celery -A workers.celery_worker beat --loglevel=info   (schedule lives in app/core/celery_app.py)"""
from app.core.celery_app import celery_app  # noqa: F401
