"""Compatibility imports for Celery benchmark ingestion metrics."""

from evaluation.metrics.ingestion import distribution, percentile, summarize_runs

__all__ = ["distribution", "percentile", "summarize_runs"]
