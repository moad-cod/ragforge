"""Select an execution profile from durable ingestion metadata.

The planner lives in the backend so Airflow and pipeline jobs consume the same
decision instead of maintaining their own chunker-name switch statements.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.chunkers.registry import get_chunker_definition


@dataclass(frozen=True)
class IngestionPlan:
    technique_id: str
    source_type: str
    profile: str
    command_suffix: str
    resource_class: str
    embedding_batch_size: int
    max_parallelism: int
    rationale: str
    requires_llm: bool
    requires_embedding_model: bool
    requires_multimodal: bool

    def as_dict(self) -> dict:
        return asdict(self)


def build_ingestion_plan(
    chunker_id: str | None,
    *,
    source_type: str | None = None,
) -> IngestionPlan:
    """Classify a chunker and return safe execution/resource hints."""
    definition = get_chunker_definition(chunker_id or "paragraph")
    normalized_source = (source_type or "file").strip() or "file"

    if definition.requires_multimodal or normalized_source == "multimodal":
        profile = "multimodal"
        resource_class = "gpu"
        embedding_batch_size = 2
        max_parallelism = 1
        rationale = "Visual page embeddings are GPU/memory intensive and use small batches."
    elif definition.requires_llm:
        profile = "llm_enriched"
        resource_class = "network"
        embedding_batch_size = 32
        max_parallelism = 1
        rationale = "LLM-backed chunking is rate-limit sensitive and produces many small chunks."
    elif definition.requires_embedding_model:
        profile = "embedding_aware"
        resource_class = "high_memory_cpu"
        embedding_batch_size = 48
        max_parallelism = 1
        rationale = "Chunking already loads an embedding model, so bounded batches limit peak memory."
    elif definition.id == "hierarchical":
        profile = "structured"
        resource_class = "cpu"
        embedding_batch_size = 96
        max_parallelism = 2
        rationale = "Parent/child structure benefits from moderate batches without excessive memory use."
    else:
        profile = "throughput"
        resource_class = "cpu"
        embedding_batch_size = 192
        max_parallelism = 4
        rationale = "Lightweight deterministic chunking can use larger embedding batches."

    return IngestionPlan(
        technique_id=definition.id,
        source_type=normalized_source,
        profile=profile,
        command_suffix=profile.upper(),
        resource_class=resource_class,
        embedding_batch_size=embedding_batch_size,
        max_parallelism=max_parallelism,
        rationale=rationale,
        requires_llm=definition.requires_llm,
        requires_embedding_model=definition.requires_embedding_model,
        requires_multimodal=(
            definition.requires_multimodal or normalized_source == "multimodal"
        ),
    )
