"""Celery worker entrypoint.

Run with:
    celery -A worker worker --loglevel=INFO
"""

from app.services.celery_app import celery_app


app = celery_app
