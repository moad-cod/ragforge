"""Compatibility Celery worker entrypoint.

Run with:
    celery -A app.workers.celery_app:celery_app worker --loglevel=INFO
"""

from app.workers.celery_app import celery_app


app = celery_app
