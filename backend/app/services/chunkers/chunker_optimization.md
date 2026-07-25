# RAGForge Chunking System — Production Refactor and Research-Aligned Optimization

You are a senior Python, information-retrieval, RAG, and distributed-systems engineer.

Your task is to inspect, refactor, test, benchmark, and document the complete RAGForge chunking subsystem.

Do not perform superficial formatting changes. Implement a production-grade chunking architecture that is:

* Correct
* Deterministic where possible
* Configurable
* Observable
* Backward-compatible where practical
* Safe under malformed input
* Consistent across every ingestion path
* Evaluated using retrieval metrics
* Honest about each technique’s actual behavior
* Efficient enough for concurrent document ingestion

Do not claim that any implementation is “100% accurate.” Instead, make correctness enforceable through validation, automated tests, benchmarks, deterministic behavior, and explicit acceptance criteria.

---

# 1. Current system to inspect

Start by reading the entire repository, especially:

```text
app/services/chunkers/
app/services/chunkers/registry.py
app/services/chunkers/tokenize.py
app/services/embeddings/
app/services/ingestion/
app/services/indexing/
app/api/
dags/
jobs/
tests/
requirements.txt
docker-compose.yml
```

Search for every use of:

```text
fixed_size
paragraph
sentence
semantic
hierarchical
late_chunking
proposition
multimodal
get_chunker
validate_chunker
chunk_hierarchical
chunk_with_embeddings
ingest_pdf_multimodal
```

Before changing code, create a dependency map showing:

```text
parser
  → normalized document
  → selected chunker
  → Silver artifact
  → embedding
  → Qdrant indexing
  → retrieval
```

Identify differences between:

```text
POST /ingest/file
POST /ingest/url
POST /ingest/gdrive
POST /ingest/multimodal
```

The final implementation must not silently behave differently across these ingestion paths.

---

# 2. Critical current problems

Fix the following verified design problems.

## 2.1 Paragraph chunker is incorrectly named

The current `paragraph` chunker uses whitespace-based 400-word windows. It does not preserve actual paragraphs.

Change it into a real paragraph-aware and structure-aware chunker.

Do not split paragraphs unnecessarily unless a paragraph exceeds the configured token limit.

## 2.2 Parser structure is discarded

The current pipeline joins parser sections into one string using two newlines.

Stop destroying parser lineage before chunking.

Preserve available information such as:

```text
document_id
document_version_id
source_type
source_filename
page_number
page_start
page_end
section_title
section_path
heading_level
paragraph_index
parser_name
parser_version
character offsets
token offsets
```

Do not invent metadata that the parser cannot provide. Missing values should remain explicitly nullable.

## 2.3 Hierarchical metadata is lost

The asynchronous file pipeline currently calls the common text-only `chunk()` method and loses parent/child relationships.

Make hierarchical output work consistently for:

```text
file ingestion
URL ingestion
Google Drive ingestion
direct service calls
```

## 2.4 Late chunking is not true late chunking

The existing implementation embeds sentences independently and averages their vectors.

That is not true late chunking.

Implement actual late chunking by:

1. Tokenizing the full document or a long contextual window.
2. Running the embedding transformer over the full token sequence.
3. Retaining contextualized token hidden states.
4. Mapping chunk character spans to token spans.
5. Pooling each chunk’s contextualized token vectors.
6. L2-normalizing the resulting chunk vectors.
7. Returning aligned chunk text, metadata, and vectors.

Do not silently fall back to independently generated sentence embeddings.

When true late chunking cannot run because the selected backend does not expose token-level hidden states, return a clear capability error or use an explicitly named approximation mode.

## 2.5 Semantic chunking can lose content

The current semantic implementation discards short semantic groups.

No non-empty source content may disappear silently.

Merge undersized groups with the most suitable adjacent group while respecting the maximum token limit.

## 2.6 Multimodal is not part of the common contract

Multimodal ingestion is a dedicated PDF page workflow but is registered like an ordinary text chunker.

Represent this distinction explicitly in the type system and registry.

Do not pretend multimodal accepts `chunk(text) -> list[str]`.

---

# 3. Research principles to follow

Use the following research as design guidance, not as permission to copy implementations blindly:

```text
Late Chunking: Contextual Chunk Embeddings Using Long-Context
Embedding Models
arXiv: 2409.04701

Dense X Retrieval: What Retrieval Granularity Should We Use?
arXiv: 2312.06648

ColPali: Efficient Document Retrieval with Vision Language Models
arXiv: 2407.01449

A Systematic Investigation of Document Chunking Strategies
and Embedding Sensitivity
arXiv: 2603.06976

Evaluating Chunking Strategies for Retrieval-Augmented
Generation on Academic Texts
arXiv: 2607.01852
```

Apply these principles:

1. Chunking must be evaluated with the actual embedding model and corpus.
2. Advanced chunking is not automatically better than simple baselines.
3. Structure should be preserved whenever reliable parser structure exists.
4. Retrieval units must remain traceable to their original source.
5. Small retrieval units may improve precision but increase index size and latency.
6. Large chunks may preserve context but reduce retrieval specificity.
7. Chunking parameters must be configurable and benchmarked.
8. True late chunking requires contextual token representations before pooling.
9. Proposition retrieval should produce atomic, self-contained facts.
10. Visual document retrieval must preserve page layout and multi-vector representations.

---

# 4. Introduce a unified typed data model

Replace the architecture where every chunker is forced to return only `list[str]`.

Create typed models similar to the following, adapting names to the existing codebase conventions:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class DocumentSection:
    text: str
    section_index: int

    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None
    section_path: tuple[str, ...] = ()
    heading_level: int | None = None

    char_start: int | None = None
    char_end: int | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    chunk_id: str
    text: str
    chunk_index: int
    chunk_type: Literal[
        "text",
        "parent",
        "child",
        "proposition",
        "page",
    ]

    content_hash: str
    strategy_id: str
    strategy_version: str

    document_id: str | None = None
    document_version_id: str | None = None

    parent_id: str | None = None

    char_start: int | None = None
    char_end: int | None = None
    token_start: int | None = None
    token_end: int | None = None

    page_start: int | None = None
    page_end: int | None = None

    section_title: str | None = None
    section_path: tuple[str, ...] = ()

    dense_vector: list[float] | None = None
    multivector: list[list[float]] | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChunkingResult:
    chunks: tuple[ChunkRecord, ...]
    warnings: tuple[str, ...] = ()
    metrics: dict[str, int | float | str] = field(default_factory=dict)
```

Also create a typed request/context model containing:

```text
document ID
document version ID
sections
strategy configuration
tokenizer
embedding backend
maximum model input length
language
cancellation or timeout context where supported
```

## Backward compatibility

Keep a temporary adapter:

```python
def chunk(text: str, ...) -> list[str]:
    ...
```

It should call the new typed implementation and return chunk text only.

Mark this compatibility interface as deprecated in documentation. Do not use it internally for new ingestion code.

---

# 5. Deterministic IDs and idempotency

Replace random chunk UUID generation with deterministic IDs.

Use stable input fields such as:

```text
document_version_id
strategy_id
strategy_version
chunk_type
parent_id
chunk_index
normalized content hash
source offsets
```

A suitable approach is UUIDv5 or a deterministic cryptographic hash.

Requirements:

* Reprocessing the same document version with the same strategy and configuration must produce identical chunk IDs.
* Changing source content must change the relevant chunk IDs.
* Changing the strategy version or meaningful configuration must produce a new identity.
* Retrying a failed ingestion must not create duplicate Qdrant points.
* Parent IDs must remain stable across retries.
* Child IDs must remain stable across retries.

Create tests proving these properties.

---

# 6. Configuration architecture

Create validated Pydantic configuration models.

Example:

```python
class BaseChunkerConfig(BaseModel):
    min_tokens: int = Field(default=20, ge=1)
    max_tokens: int = Field(default=512, ge=8)
    overlap_tokens: int = Field(default=50, ge=0)
    preserve_headings: bool = True
    preserve_lists: bool = True
    include_heading_context: bool = True
```

Each strategy must have its own configuration model.

Reject invalid values before processing.

Examples of invalid configurations:

```text
overlap_tokens >= max_tokens
minimum size > maximum size
parent size <= child size when not supported
negative thresholds
similarity threshold outside its valid range
zero batch size
unsupported pooling mode
unsupported model capability
```

Remove hard-coded production parameters from chunker functions.

Load defaults from one centralized configuration layer.

Allow per-project or per-ingestion overrides only through validated fields.

Record the effective configuration in chunk metadata or ingestion-run metadata.

---

# 7. Shared text normalization and token accounting

Create shared utilities for:

```text
Unicode normalization
line-ending normalization
whitespace normalization
paragraph detection
heading detection
list-item detection
sentence segmentation
token counting
character-to-token span alignment
content hashing
```

Do not globally flatten all whitespace because that destroys document structure.

Use the tokenizer associated with the target embedding or generation model when available.

Provide a controlled fallback tokenizer for offline tests.

Do not use character count or word count as if they were exact model-token counts.

Every produced text chunk must be checked against its configured token budget.

---

# 8. Strategy-specific implementation

## 8.1 Fixed-size baseline

Keep this strategy as a simple, fast baseline, but make it token-aware.

Requirements:

* Split using tokens instead of raw character count.
* Validate overlap.
* Guarantee forward progress.
* Prefer natural boundaries near the target limit:

  1. Section boundary
  2. Paragraph boundary
  3. Sentence boundary
  4. Whitespace
  5. Hard token boundary
* Preserve source offsets.
* Never create infinite loops.
* Never create empty chunks.
* Do not discard short final chunks automatically.
* Merge a short final chunk with its predecessor when safe.
* Expose all sizes through configuration.

The baseline must remain fast enough for throughput-oriented ingestion.

## 8.2 Paragraph and structure-aware chunking

Make `paragraph` a real paragraph-aware strategy.

Algorithm:

1. Consume structured parser sections.
2. Detect paragraphs without destroying blank-line boundaries.
3. Keep headings attached to their following content.
4. Keep list items together when they fit.
5. Greedily group adjacent paragraphs up to `max_tokens`.
6. Split oversized paragraphs by sentences.
7. Split oversized sentences only as a last resort.
8. Optionally prepend the relevant heading path as retrieval context.
9. Preserve original text separately from any contextualized embedding text.

Do not duplicate heading text in the user-visible citation unless explicitly intended.

Return page and section lineage.

## 8.3 Sentence strategy

Do not return every sentence as an isolated chunk by default.

Support two modes:

```text
single_sentence
sentence_window
```

The production default should group adjacent sentences into token-bounded windows.

Requirements:

* Preserve short factual sentences.
* Preserve headings, captions, labels, and list items.
* Use language-aware sentence tokenization where available.
* Keep the regex tokenizer only as an explicit fallback.
* Emit a warning metric when fallback tokenization is used.
* Support configurable sentence overlap.
* Respect maximum token size.

## 8.4 Semantic chunking

Replace the previous-sentence-only algorithm with a more robust, configurable design.

Recommended process:

1. Sentence-segment the section.
2. Build buffered sentence units such as:

   ```text
   previous sentence + current sentence + next sentence
   ```
3. Embed units in batches.
4. Calculate adjacent semantic distance.
5. Select breakpoints using one configurable method:

   ```text
   fixed similarity threshold
   distance percentile
   standard-deviation threshold
   interquartile-range threshold
   ```
6. Build initial groups.
7. Merge undersized groups with the semantically closest neighbor.
8. Split oversized groups at the strongest internal breakpoint.
9. Enforce final token constraints.
10. Preserve all content and lineage.

Do not assume semantic chunking is always superior.

Expose:

```text
embedding model
breakpoint method
threshold
buffer size
minimum tokens
target tokens
maximum tokens
batch size
```

Cache repeated sentence embeddings within one ingestion run when safe.

Do not recompute the same embedding unnecessarily.

## 8.5 Hierarchical chunking

Make the hierarchy structure-aware instead of only grouping fixed sentence counts.

Preferred hierarchy:

```text
document
  → section parent
    → paragraph-group child
      → optional sentence-level leaf
```

Use parser headings and sections when available.

When structural metadata is unavailable, use a documented fallback based on token-bounded paragraph groups.

Requirements:

* Deterministic parent and child IDs.
* Global child indexes, plus optional indexes local to the parent.
* Parent records must contain broad context.
* Child records must contain focused retrieval units.
* Children must reference their parent.
* Qdrant payloads must preserve the relationship.
* Retrieval should be able to retrieve children and expand to parent context.
* All ingestion paths must use the same specialized result.
* Do not flatten hierarchical output into strings inside the internal pipeline.

Add an optional retrieval mode:

```text
retrieve child
→ fetch parent
→ return parent or parent-plus-neighbor context
```

Prevent duplicate parent text from overwhelming the final generation context.

## 8.6 True late chunking

Implement true late chunking in a separate optional model-backed component.

Requirements:

* Use a Hugging Face or equivalent backend that exposes contextual token hidden states.
* Confirm the selected model supports the required input length.
* Tokenize with offset mappings.
* Run the complete long context through the encoder before chunk pooling.
* Produce chunk boundaries using structure-aware or token-aware rules.
* Map each chunk’s character span to contextual token spans.
* Mean-pool or use another explicitly configured pooling method.
* Apply attention-mask-aware pooling.
* Exclude special tokens from chunk pooling.
* L2-normalize vectors.
* Return vectors aligned one-to-one with chunk records.
* Do not perform another dense embedding pass in Gold indexing.
* Record model ID, model revision, pooling method, dimension, and strategy version.
* Use inference mode and disable gradients.
* Use mixed precision only where supported.
* Batch documents safely without mixing span mappings.

For documents longer than the model context:

* Use overlapping long-context windows.
* Map each chunk to the window that provides the strongest surrounding context.
* Avoid averaging unrelated duplicated representations without documentation.
* Record which contextual window generated each vector.

Keep an explicitly named approximation only when needed:

```text
late_chunking_approx
```

Never describe independently embedded and averaged sentences as true late chunking.

## 8.7 Proposition chunking

Implement proposition extraction as a reliable enrichment pipeline.

Requirements:

* Use a configurable provider and model.
* Do not hard-code one provider-specific model name in business logic.
* Use structured JSON output or JSON schema when supported.
* Validate the output with Pydantic.
* Preserve the source paragraph and offsets for every proposition.
* Create deterministic proposition IDs.
* Keep each proposition concise, atomic, self-contained, and faithful to the source.
* Do not introduce information absent from the source.
* Remove duplicates using normalized exact matching first.
* Make semantic deduplication optional and threshold-controlled.
* Do not discard headings or short facts before determining their value.
* Add token limits before sending source text to the model.
* Batch compatible requests where the provider supports it.
* Add bounded retries with exponential backoff and jitter.
* Respect provider retry headers.
* Add timeout handling.
* Add concurrency limits.
* Add request-level caching based on:

  ```text
  source content hash
  prompt version
  model ID
  model revision
  extraction configuration
  ```
* Never log API keys or sensitive document content at normal log levels.

Fallback hierarchy:

```text
validated propositions
→ sentence-window fallback
→ original paragraph fallback
```

Record the fallback reason in metadata.

A document should not fail completely because one paragraph fails, but partial failures must be visible in ingestion metrics.

## 8.8 Multimodal page retrieval

Keep multimodal ingestion as a specialized strategy type.

Requirements:

* Accept PDFs through the dedicated typed interface.
* Render pages with configurable DPI and pixel limits.
* Reject encrypted, malformed, oversized, or unsupported PDFs safely.
* Add maximum:

  ```text
  pages
  rendered pixels
  source bytes
  processing time
  ```
* Keep rendering, embedding, object upload, and Qdrant indexing separately observable.
* Use GPU batching when available.
* Refuse or warn clearly before extremely expensive CPU execution.
* Run inference without gradients.
* Preserve page number, image URL, dimensions, model revision, and document version.
* Store the page’s multi-vector representation as one logical Qdrant point.
* Use the correct late-interaction or MaxSim scoring behavior.
* Ensure query and document embeddings use compatible models and dimensions.
* Clean up uploaded page images if later indexing fails.
* Make cleanup idempotent.
* Support a two-stage retrieval option:

  ```text
  cheap candidate retrieval
  → multivector reranking
  ```
* Make vector compression, token pruning, or pooling optional and benchmarked.
* Never enable lossy compression by default without measuring retrieval impact.

Keep heavy dependencies in a separate optional installation group or worker image.

Example:

```text
requirements-base.txt
requirements-llm.txt
requirements-multimodal.txt
```

or equivalent optional dependency groups in `pyproject.toml`.

---

# 9. Registry redesign

Make registry metadata describe real behavior.

Each registry definition should include typed fields similar to:

```text
id
display_name
description
tier
status
strategy_kind
input_kind
output_kind
deterministic
supports_overlap
preserves_structure
returns_embeddings
returns_multivectors
requires_network
requires_gpu
requires_optional_dependencies
default_config
config_schema
runtime_profile
strategy_version
```

Use enums rather than arbitrary strings where practical.

Suggested distinctions:

```text
strategy_kind:
  text
  hierarchical
  llm_enriched
  contextual_embedding
  multimodal

input_kind:
  text
  structured_sections
  pdf_bytes

output_kind:
  text_chunks
  hierarchical_chunks
  chunks_with_vectors
  propositions
  page_multivectors
```

Validate the registry at application startup.

Tests must fail when:

* Duplicate IDs exist.
* Multiple defaults exist.
* No default exists.
* A callable cannot be imported.
* The callable’s declared capabilities do not match its actual result type.
* An optional dependency is missing but the strategy is incorrectly shown as available.
* Registry descriptions contain false capability claims.

`GET /chunkers` should expose availability and a user-safe reason when a strategy is unavailable.

Example:

```json
{
  "id": "multimodal",
  "available": false,
  "unavailable_reason": "Multimodal worker dependencies are not installed."
}
```

Do not expose secrets, internal import paths, or exception traces.

---

# 10. Unify ingestion behavior

Refactor ingestion so all source types go through one orchestration contract:

```text
source acquisition
→ parser
→ structured document
→ chunker execution
→ Silver persistence
→ embedding if not already produced
→ Qdrant indexing
→ status update
```

Source-specific code should only acquire and parse the source.

It should not contain separate implementations of hierarchical or late-chunking behavior.

The same document and configuration must produce equivalent chunk records regardless of whether the source entered through file, URL, or Google Drive ingestion.

Multimodal PDF ingestion can remain specialized, but it must use the same run-status, idempotency, error, cleanup, and observability conventions.

---

# 11. Silver and Qdrant schema

Extend Silver records to preserve:

```text
chunk_id
document_id
document_version_id
chunk_index
chunk_type
parent_id
text
embedding_text when different
content_hash
strategy_id
strategy_version
effective configuration hash
char_start
char_end
token_start
token_end
token_count
page_start
page_end
section_title
section_path
source filename
parser name
parser version
fallback reason
created_at
```

Store vectors only where the strategy precomputes them.

Do not serialize absent vectors as invalid placeholder arrays.

Create a migration plan for existing Silver artifacts and database records.

Qdrant point IDs must use deterministic chunk IDs.

Create payload indexes only for fields used in filtering, such as:

```text
organization_id
project_id
document_id
document_version_id
chunk_type
parent_id
strategy_id
```

Maintain strict tenant filters in every search and retrieval operation.

---

# 12. Embedding and retrieval integration

Ensure chunking is evaluated as part of the complete retrieval system.

Support:

```text
dense retrieval
sparse retrieval
hybrid dense + sparse retrieval
optional reranking
parent expansion
multivector late interaction
```

For Qdrant hybrid retrieval, use a supported fusion strategy such as RRF or an existing project-approved fusion implementation.

Do not change the retrieval stack unnecessarily if the project already has a correct implementation.

Avoid embedding a chunk twice.

Before requesting embeddings, check whether `ChunkRecord` already contains a valid vector produced by the chunker.

Validate:

```text
vector dimension
model identity
model revision
normalization expectation
distance metric
```

Fail clearly when incompatible vectors are passed to an existing collection.

---

# 13. Concurrency, reliability, and resource safety

All strategies must operate safely when many users upload documents concurrently.

Requirements:

* No mutable process-wide request state.
* Thread-safe or process-safe lazy model initialization.
* Bounded embedding batches.
* Bounded LLM concurrency.
* Bounded multimodal GPU concurrency.
* Explicit timeouts.
* Retry only transient failures.
* Do not retry validation errors.
* Support cancellation where the existing worker system allows it.
* Release document and image objects after use.
* Avoid keeping complete document copies unnecessarily.
* Avoid repeated tokenizer or model loading.
* Do not download tokenizer data during a production request.
* Pin model revisions where reproducibility is required.
* Provide worker-level resource profiles for CPU, high-memory CPU, network/LLM, and GPU execution.

Add a warm-up mechanism for heavy models, but do not block lightweight API catalog endpoints while loading them.

---

# 14. Observability

Add structured metrics for every chunking run:

```text
strategy ID
strategy version
document size
input characters
input tokens
section count
output chunk count
minimum chunk tokens
maximum chunk tokens
average chunk tokens
p50 chunk tokens
p95 chunk tokens
discarded content count
merged group count
split group count
fallback count
tokenizer fallback used
embedding calls
embedding batch count
LLM calls
LLM retries
LLM failures
rendered page count
processing duration by stage
estimated or actual external cost where available
```

The expected discarded non-whitespace content count is zero.

Add structured logs using IDs, counts, durations, and failure classes.

Do not log complete private document text.

---

# 15. Tests

Create comprehensive automated tests.

## 15.1 Unit tests

Test every strategy with:

```text
blank input
whitespace-only input
one short sentence
short factual list item
heading followed by content
multiple paragraphs
extremely long paragraph
extremely long sentence
Unicode text
Arabic text
French text
English abbreviations
decimal numbers
URLs
Markdown lists
tables represented as text
missing NLTK data
invalid configuration
maximum overlap
document exactly at token limit
document one token over limit
```

## 15.2 Property-based tests

Use Hypothesis where appropriate.

Prove invariants such as:

* No infinite loop.
* No empty chunks.
* Every chunk is within the configured maximum token size, except explicitly documented unavoidable cases.
* Output ordering follows source ordering.
* Source offsets are monotonic.
* Reconstructed source coverage does not silently lose non-whitespace content.
* Deterministic strategies return identical outputs on repeated runs.
* Deterministic IDs remain identical across retries.
* Parent references always resolve.
* Vectors and text chunks have equal aligned lengths.
* Normalized vectors have approximately unit L2 norm.
* Invalid configurations always fail before processing.

## 15.3 Integration tests

Test:

```text
parser → chunker → Silver
Silver → embedding → Qdrant
hierarchical child → parent expansion
late chunking → vector reuse
proposition partial failure → fallback
multimodal page → object storage → Qdrant
retry after partial failure
document re-ingestion
document version update
tenant isolation
```

Use test containers or existing Docker services when practical.

Do not require external paid APIs in the default test suite.

Use provider fakes for proposition extraction.

Use a lightweight fake model for token-span late-chunking tests, plus an optional real-model integration test.

## 15.4 Golden tests

Create stable fixtures containing:

```text
technical documentation
legal-style sections
academic text
FAQ content
Markdown
scanned or visual PDF sample
```

Store expected boundaries or validated invariants.

Avoid fragile tests that depend on random UUIDs or unpinned remote model output.

---

# 16. Retrieval evaluation benchmark

Create a benchmark command such as:

```bash
python -m benchmarks.chunking.evaluate \
  --dataset tests/fixtures/retrieval_dataset.jsonl \
  --strategies fixed_size,paragraph,sentence,semantic,hierarchical,late_chunking,proposition \
  --output artifacts/chunking-report.json
```

The benchmark dataset should contain:

```text
document
query
relevant document ID
relevant evidence span
optional answer
domain
language
```

Report at minimum:

```text
Recall@1
Recall@5
Recall@10
MRR
nDCG@5
evidence-span coverage
chunk count
index vector count
average chunk size
p95 chunk size
ingestion latency
embedding latency
retrieval latency
peak memory when measurable
external LLM calls
estimated cost
```

Evaluate each strategy with the same:

```text
corpus
queries
embedding model
Qdrant configuration
retrieval top-k
reranker configuration
```

Do not declare a new default strategy unless it demonstrates a meaningful improvement on representative RAGForge data without unacceptable cost or latency.

Keep `fixed_size` and the corrected `paragraph` strategy as baselines.

Generate:

```text
JSON report
CSV summary
human-readable Markdown report
```

---

# 17. Performance optimization

Profile before optimizing.

Investigate:

```text
sentence tokenization time
token counting
embedding batching
duplicate embedding work
model loading
serialization
Parquet writing
Qdrant upserts
PDF rendering
GPU transfer
LLM request concurrency
```

Apply optimizations only when supported by measurements.

Likely improvements include:

* Cache tokenizer objects.
* Cache embedding model instances safely.
* Batch embedding requests.
* Reuse vectors generated by late chunking.
* Avoid joining and copying full document strings repeatedly.
* Stream or incrementally process large structured documents where compatible.
* Use efficient NumPy or tensor operations for similarity calculations.
* Avoid Python loops over vector dimensions.
* Use inference mode.
* Use bounded worker queues.
* Upsert Qdrant points in controlled batches.
* Store configuration hashes to prevent unnecessary reprocessing.

Do not introduce premature distributed complexity.

---

# 18. Security requirements

Validate all external input.

For uploaded PDFs and text:

* Enforce size limits.
* Enforce page limits.
* Handle malformed files.
* Do not execute embedded content.
* Sanitize object-storage paths.
* Avoid path traversal.
* Do not trust provided filenames.
* Do not expose internal storage URLs when signed URLs are required.
* Do not log credentials.
* Do not include secrets in task payloads unnecessarily.

For proposition extraction:

* Treat document text as untrusted data, not instructions.
* Use a prompt that explicitly prevents source text from changing system behavior.
* Validate structured output.
* Keep tenant data isolated.
* Never reuse cache results across tenants unless the cache key and security design explicitly permit it.

---

# 19. Documentation

Update documentation so it reflects actual implementation.

For every strategy document:

```text
real algorithm
input type
output type
configuration
dependencies
determinism
resource profile
failure behavior
fallback behavior
metadata preservation
retrieval integration
known limitations
recommended use cases
cases where it should not be used
```

Remove marketing claims such as “best,” “ultimate,” or “precision” unless they are clearly presented as product tier labels rather than technical guarantees.

Explain that chunking quality is corpus-dependent and must be evaluated.

Update API schemas and frontend-facing registry descriptions.

---

# 20. Migration and compatibility

Do not break existing clients without a migration path.

Provide:

1. A list of changed interfaces.
2. Compatibility adapters.
3. Database migrations.
4. Silver schema migration.
5. Qdrant reindex requirements.
6. Feature flags where rollout risk exists.
7. Deprecation warnings.
8. A rollback procedure.

Existing public chunker IDs should remain valid unless there is a strong technical reason to change one.

When a strategy’s meaning changes materially, increment `strategy_version`.

For the previous incorrect late-chunking implementation:

* Preserve it temporarily under an explicitly accurate name such as `late_chunking_approx`.
* Implement true late chunking under `late_chunking`.
* Mark old indexed data with its original strategy version.
* Do not mix vectors generated by the two algorithms without explicit reindexing.

---

# 21. Required execution process

Work in this order:

## Phase 1 — Audit

Produce:

```text
current architecture map
call-site inventory
data-loss points
duplicate implementations
incorrect capability descriptions
test coverage gaps
dependency and runtime risks
```

## Phase 2 — Design

Produce a concise design note covering:

```text
new typed contract
configuration models
strategy interfaces
metadata lineage
deterministic IDs
ingestion unification
migration approach
```

## Phase 3 — Core implementation

Implement:

```text
typed data models
shared utilities
registry validation
configuration validation
backward-compatible adapters
```

## Phase 4 — Strategy refactors

Refactor one strategy at a time.

After each strategy:

1. Run focused tests.
2. Run type checking.
3. Run linting.
4. Report changed behavior.
5. Confirm that no source content is silently lost.

## Phase 5 — Ingestion integration

Unify all ingestion paths.

## Phase 6 — Storage and retrieval integration

Update Silver and Qdrant mapping.

## Phase 7 — Tests and benchmarks

Add the full test and evaluation suite.

## Phase 8 — Documentation and migration

Complete docs, migrations, and rollout instructions.

---

# 22. Coding standards

Use:

```text
Python 3.12
full type hints
small cohesive modules
dataclasses or Pydantic models
explicit exceptions
structured logging
dependency injection
pure functions where possible
async only where it provides actual benefit
```

Avoid:

```text
catching Exception without classification
silent fallbacks
random IDs for deterministic artifacts
mutable default arguments
global request state
duplicated ingestion logic
hard-coded model names
hard-coded chunk sizes
unbounded retries
unbounded concurrency
blocking network calls inside async routes
loading heavy models during registry listing
```

Run the project’s existing formatter, linter, and type checker.

Do not suppress type errors with broad `# type: ignore` comments unless individually justified.

---

# 23. Definition of done

The work is complete only when all of the following are true:

* All eight public strategies have truthful registry metadata.
* Paragraph chunking preserves real paragraph structure.
* Generic ingestion preserves parser lineage.
* No chunker silently loses meaningful source content.
* Invalid overlap cannot create an infinite loop.
* Hierarchical relationships survive every ingestion path.
* Hierarchical IDs are deterministic.
* True late chunking uses contextual token states before pooling.
* Approximate late chunking is labeled accurately.
* Precomputed vectors are not embedded twice.
* Proposition extraction has schema validation, retries, caching, and provenance.
* Multimodal ingestion has resource limits and idempotent cleanup.
* All Qdrant writes use deterministic point IDs.
* Tenant filters are enforced in retrieval.
* Unit, property, integration, and golden tests pass.
* Static type checking passes.
* Linting passes.
* The benchmark command runs reproducibly.
* Documentation matches the implementation.
* A migration and rollback plan exists.
* Existing APIs remain compatible or have documented versioned replacements.

---

# 24. Required final Codex response

At the end, provide:

```text
1. Audit findings
2. Architecture changes
3. Files created
4. Files modified
5. Database and storage migrations
6. Strategy-by-strategy changes
7. Tests added
8. Benchmark results
9. Performance measurements
10. Remaining limitations
11. Commands to run locally
12. Commands to run through Docker
13. Reindexing instructions
14. Rollback instructions
```

Include exact commands.

Do not say “everything works” without showing the executed test, lint, type-check, integration, and benchmark results.

When a command cannot be executed in the current environment, state that explicitly and provide the exact command the developer must run.

Begin by auditing the repository. Do not modify implementation files until the dependency map and change plan are complete.
