"""Canonical lifecycle values shared by control-plane models."""

DOCUMENT_STATUSES = frozenset(
    {
        "uploaded",
        "landed",
        "processing",
        "chunked",
        "embedded",
        "indexed",
        "failed",
        "deleted",
    }
)

INGESTION_RUN_STATUSES = frozenset(
    {
        "landed",
        "queued",
        "running",
        "silver_completed",
        "gold_completed",
        "indexed",
        "failed",
        "cancelled",
    }
)

EMBEDDING_RUN_STATUSES = frozenset(
    {
        "queued",
        "loading_model",
        "running",
        "retrying",
        "completed",
        "failed",
        "cancelled",
    }
)


def status_check_sql(column_name: str, values: frozenset[str]) -> str:
    """Build a deterministic SQL CHECK expression for a status column."""
    allowed = ", ".join(f"'{value}'" for value in sorted(values))
    return f"{column_name} IN ({allowed})"


def validate_status(value: str, allowed: frozenset[str], field_name: str = "status") -> str:
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"Invalid {field_name} {value!r}; expected one of: {choices}")
    return value
