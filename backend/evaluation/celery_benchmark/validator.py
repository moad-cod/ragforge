"""API-visible hard-gate validation for Celery ingestion runs."""

from __future__ import annotations

from typing import Any

from evaluation.celery_benchmark.models import ValidationResult, WorkloadDocument


TERMINAL_STATUSES = {"indexed", "failed", "cancelled"}
REQUIRED_PROGRESS = ("bronze", "silver", "gold", "qdrant")


def validate_indexed_run(
    *,
    workload: WorkloadDocument,
    upload_payload: dict[str, Any],
    run_payload: dict[str, Any] | None,
    versions: list[dict[str, Any]],
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    observed: dict[str, Any] = {
        "upload_status": upload_payload.get("status"),
        "run_status": run_payload.get("status") if run_payload else None,
        "version_count": len(versions),
    }
    if not run_payload:
        errors.append("Run never returned a terminal status payload")
        return ValidationResult(False, errors=errors, warnings=warnings, observed=observed)

    if upload_payload.get("status") != "landed":
        errors.append(f"Upload status was {upload_payload.get('status')!r}, expected 'landed'")
    if run_payload.get("status") != "indexed":
        errors.append(f"Run status was {run_payload.get('status')!r}, expected 'indexed'")
    if run_payload.get("document_id") != upload_payload.get("document_id"):
        errors.append("Run document_id does not match upload document_id")
    if run_payload.get("document_version_id") != upload_payload.get("document_version_id"):
        errors.append("Run document_version_id does not match upload document_version_id")
    progress = run_payload.get("progress") or {}
    missing_progress = [key for key in REQUIRED_PROGRESS if progress.get(key) is not True]
    if missing_progress:
        errors.append(f"Progress gates are incomplete: {', '.join(missing_progress)}")

    matching_versions = [
        version
        for version in versions
        if version.get("document_version_id") == upload_payload.get("document_version_id")
    ]
    if not matching_versions:
        errors.append("Uploaded document version is missing from /documents/{id}/versions")
    else:
        version = matching_versions[0]
        observed["version_status"] = version.get("status")
        observed["bronze_path"] = version.get("bronze_path")
        observed["silver_path"] = version.get("silver_path")
        observed["gold_path"] = version.get("gold_path")
        if version.get("status") != "indexed":
            errors.append(f"Document version status was {version.get('status')!r}, expected 'indexed'")
        for path_key in ("bronze_path", "silver_path", "gold_path"):
            if not version.get(path_key):
                errors.append(f"Document version is missing {path_key}")
        if version.get("chunker_id") != workload.chunker:
            warnings.append(
                f"Document version chunker is {version.get('chunker_id')!r}; workload used {workload.chunker!r}"
            )

    return ValidationResult(not errors, errors=errors, warnings=warnings, observed=observed)
