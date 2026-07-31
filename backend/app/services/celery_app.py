"""Compatibility import for the Celery app.

The worker runtime now lives in ``app.workers``.
"""

from app.workers.celery_app import celery_app

__all__ = ["celery_app"]
