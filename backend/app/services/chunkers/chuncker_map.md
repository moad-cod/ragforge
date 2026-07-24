# RAGForge Chunker Map

This document maps the implementation in `app/services/chunkers/` as it exists
today. It describes the callable methods, produced data, dependencies,
ingestion behavior, and practical limitations of each chunker.

## Package role

Text parsers return a list of extracted sections. RAGForge joins those sections
with two newlines and passes the resulting string to the selected chunker. Most
chunkers implement this common interface:

```python
def chunk(text: str, ...) -> list[str]
```

The resulting text chunks are embedded and indexed with dense and sparse
vectors. `hierarchical`, `late_chunking`, and `multimodal` also expose
specialized methods for richer output.

There are eight public chunkers:

| ID | Display name | Tier | Status | Main boundary type | Runtime profile |
|---|---|---|---|---|---|
| `fixed_size` | Starter Chunking | base | stable | Character windows | throughput |
| `paragraph` | Base Chunking | base | stable, default | Paragraph packing and oversized word windows | throughput |
| `sentence` | Precision Chunking | pro | stable | Sentence-aligned groups | throughput |
| `semantic` | Semantic Chunking | pro | beta | Adjacent-sentence similarity | embedding-aware |
| `hierarchical` | Structured Chunking | business | beta | Fixed sentence groups with parent/child records | structured |
| `late_chunking` | Pooled Sentence Chunking | ultimate | beta | Fixed sentence groups with pooled embeddings | embedding-aware |
| `proposition` | Ultimate Chunking | ultimate | beta | LLM-extracted atomic propositions | LLM-enriched |
| `multimodal` | Multimodal Chunking | ultimate | experimental | Rendered PDF pages | multimodal |

## Capability matrix

| Chunker | Deterministic | Overlap | Preserves structure | External model/service | Specialized output |
|---|---:|---:|---:|---|---|
| `fixed_size` | Yes | 50 characters by default | No | None | No |
| `paragraph` | Yes | 50 words for oversized paragraphs | Natural paragraph boundaries | None | No |
| `sentence` | Yes for a fixed tokenizer | No | Sentence boundaries only | NLTK tokenizer data, with regex fallback | No |
| `semantic` | Yes for a fixed embedding backend | No | Topic shifts inferred from similarity | Local embedding backend and NLTK/regex tokenizer | No |
| `hierarchical` | Yes | No | Parent/child sentence groups | NLTK/regex tokenizer | `HierarchicalChunk` relationships |
| `late_chunking` | Yes for a fixed embedding backend | No | Fixed sentence groups | Local embedding backend and NLTK/regex tokenizer | Precomputed dense vectors |
| `proposition` | No | No | Atomic facts inferred by an LLM | Groq API and API key | Parsed propositions with per-paragraph fallback |
| `multimodal` | Model-dependent | Page-level | Visual page layout | PyMuPDF, Pillow, PyTorch, ColQwen2, object storage | Multi-vector page embeddings and image URLs |

## Chunker methods

### `fixed_size.py`

#### `chunk(text, chunk_size=512, overlap=50, min_chunk_chars=1) -> list[str]`

- Splits by character count, not by tokens.
- Walks backward from the proposed boundary to avoid cutting a word.
- Makes a hard cut when no whitespace exists in the window.
- Carries `overlap` characters into the next window.
- Trims each result and retains it when it meets `min_chunk_chars`.
- Returns an empty list for blank input.
- Rejects non-positive sizes, negative overlap, and overlap greater than or
  equal to the chunk size.

Capabilities:

- Fast, local, and predictable enough for baseline experiments.
- Handles unstructured text without tokenizer or model dependencies.
- Allows direct control of approximate chunk width and overlap.

Limitations:

- Character count is only a rough proxy for model token count.
- Word-boundary backtracking can make chunk sizes uneven.
- It does not preserve paragraphs, sections, pages, or headings.

### `paragraph.py`

#### `chunk(text, chunk_size=400, overlap=50) -> list[str]`

- Splits input on natural blank-line paragraph boundaries.
- Packs whole paragraphs into chunks of at most 400 words when possible.
- Splits an oversized paragraph into 400-word windows with 50-word overlap.
- Normalizes whitespace inside each paragraph without discarding short text.
- Validates chunk size and overlap.

Capabilities:

- Fast, deterministic, dependency-free default.
- Preserves paragraph boundaries and provides overlap for oversized paragraphs.
- Works consistently after all parser sections are concatenated.

Limitations:

- Normal packed-paragraph chunks do not overlap; overlap applies only when a
  single paragraph must be split.
- Page, paragraph, heading, and section lineage are not retained.

### `sentence.py`

#### `chunk(text, min_chunk_chars=30) -> list[str]`

- Calls the shared `split_sentences()` helper.
- Emits sentence-aligned chunks.
- Accumulates adjacent short sentences until the minimum length is reached.
- Merges a short trailing fragment into the preceding chunk, so text is not
  silently discarded.

Capabilities:

- Produces small, precise retrieval units.
- Uses NLTK sentence tokenization when its data is installed.
- Remains operational through the regex fallback when NLTK data is missing.

Limitations:

- Multiple short sentences may be combined into one retrieval unit.
- There is no overlap.
- Regex fallback quality is lower for abbreviations and unusual punctuation.

### `semantic.py`

#### `_cosine_similarity(a, b) -> float`

Validates equally sized one-dimensional vectors and computes cosine similarity.
It returns zero similarity when either vector has zero norm.

#### `chunk(text, threshold=0.5, min_chunk_len=50) -> list[str]`

- Sentence-splits the input without dropping short sentences.
- Embeds all retained sentences in one backend call.
- Validates the embedding count and shape.
- Compares each sentence embedding only with the immediately previous one.
- Keeps adjacent sentences together while similarity is at least `threshold`.
- Starts a new chunk below the threshold.
- Merges groups shorter than `min_chunk_len` into adjacent content.
- Validates threshold and length parameters.

Capabilities:

- Finds local topic changes without calling an LLM.
- Uses the configured embedding backend: FastEmbed
  `BAAI/bge-small-en-v1.5` in the normal runtime or deterministic lexical
  embeddings in offline test environments.
- Threshold and minimum output length are configurable for direct callers.

Limitations:

- It detects only adjacent-sentence changes; it does not compare against a
  running chunk centroid or global document structure.
- It has no overlap and does not preserve page or section boundaries.
- Output boundaries can change with the embedding backend or model version.

### `hierarchical.py`

#### `HierarchicalChunk`

Dataclass fields:

| Field | Meaning |
|---|---|
| `text` | Parent or child text |
| `chunk_type` | `"parent"` or `"child"` |
| `parent_id` | Parent UUID for children; `None` for parents |
| `chunk_id` | Deterministic UUIDv5 for this record |
| `index` | Parent index, or child index local to its parent |

#### `chunk(text) -> list[str]`

Calls `chunk_hierarchical()` and returns only child text. This keeps the common
text-chunker interface but removes relationship metadata.

#### `chunk_hierarchical(text, parent_size=5, child_size=2, namespace=None) -> list[HierarchicalChunk]`

- Sentence-splits the input without dropping short sentences.
- Groups every five sentences into a parent by default.
- Splits each parent into two-sentence child groups by default.
- Generates stable UUIDv5 parent and child IDs from namespace, position, and
  content. Direct ingestion supplies the document ID as the namespace.
- Validates parent and child group sizes.

Capabilities:

- Can index both broad parent context and smaller child retrieval units.
- Explicitly links children to parents.
- Produces deterministic relationship IDs for repeat processing.
- Supports configurable parent and child sentence counts for direct callers.
- Synchronous URL and Google Drive ingestion use the specialized indexing path
  and store parent/child fields in Qdrant.

Limitations:

- It is sentence-count hierarchy, not heading-, section-, or layout-aware
  hierarchy.
- The Bronze-to-Silver file pipeline calls the common `chunk()` method, so it
  currently stores only child strings and loses parent/child relationships.
- Child indexes restart at zero for every parent.

### `late_chunking.py`

#### `chunk(text, chunk_size=5, min_chunk_len=50) -> list[str]`

- Sentence-splits the input without dropping short sentences.
- Groups every five sentences into text chunks.
- Combines undersized groups with adjacent content without dropping sentences.
- Returns text without loading or running the embedding model.
- Validates chunk size and minimum length.

#### `chunk_with_embeddings(text, chunk_size=5, min_chunk_len=50) -> tuple[list[str], list[list[float]]]`

- Embeds retained sentences as a batch.
- Groups them into fixed sentence windows.
- Mean-pools each group's sentence vectors.
- L2-normalizes each pooled vector.
- Returns aligned text chunks and dense vectors.
- Validates embedding count and shape.

Capabilities:

- Produces chunk vectors during boundary construction.
- File ingestion preserves these vectors in Silver Parquet and reuses them in
  Gold, avoiding a second dense-embedding pass.
- Synchronous URL and Google Drive ingestion directly indexes the returned
  vectors.

Limitations:

- The configured BGE/FastEmbed service embeds each sentence independently.
  Passing sentences in one batch does not make their embeddings inherit
  full-document context. The implementation is therefore mean-pooled
  sentence embedding, not token-level late chunking over a single contextual
  document encoding.
- Boundaries are fixed sentence counts; embeddings do not choose the
  boundaries.
- There is no overlap or page/section preservation.

### `proposition.py`

#### `_get_client() -> Groq`

Lazily and thread-safely creates a Groq client and requires `GROQ_API_KEY`.

#### `_clean_json_text(raw) -> str`

Removes surrounding Markdown JSON fences and `<think>...</think>` blocks.

#### `_extract_json_candidate(raw) -> str`

Scans candidate JSON object/array starts and uses `JSONDecoder.raw_decode()` to
return the first value that parses successfully.

#### `_parse_propositions(raw) -> list[str]`

- Accepts a JSON list or an object containing `propositions` or `items`.
- Retains only non-empty string items.
- Rejects non-list and empty results.

#### `_status_code(exc) -> int | None`

Extracts and normalizes an HTTP status from an exception or its response.

#### `_classify_failure(exc) -> str`

Classifies rate/quota, authentication, service, JSON, and general extraction
failures for logging.

#### `chunk(text, min_paragraph_chars=50) -> list[str]`

- Splits on blank-line paragraph boundaries.
- Preserves short paragraphs directly instead of sending or discarding them.
- Sends each retained paragraph separately to Groq model
  `qwen/qwen3.6-27b`, with temperature `0` and up to 1024 output tokens.
- Requests short, self-contained facts in JSON.
- Falls back to the original paragraph when that paragraph's request or
  response parsing fails.
- Stops making further provider calls after an authentication or rate-limit
  failure and preserves the remaining paragraphs.
- Aggregates and logs failure reasons without failing the entire document.

Capabilities:

- Produces fine-grained, self-contained factual retrieval units.
- Isolates failures per paragraph.
- Tolerates common model-response wrappers and limited schema variation.
- Provides specific operational logging for quota and authentication failures.

Limitations:

- Requires network access, a Groq API key, quota, and availability.
- Cost and latency scale approximately with the number of retained paragraphs.
- Results are model-dependent even at temperature zero.
- The fallback returns a full paragraph, so output granularity may be mixed.
- Proposition strings are structurally validated, but their semantic
  correctness is not independently verified.

### `multimodal.py`

This module is registered as a chunker but does not implement the common
`chunk(text) -> list[str]` interface. It is a separate PDF page-ingestion path.

#### `_get_model()`

Lazily loads `vidore/colqwen2-v1.0`, selects CUDA when available, uses
float16 on CUDA and float32 on CPU, and thread-safely caches the model and
processor only after both load successfully.

#### `render_pdf_pages(file_bytes, dpi=150, max_pages=None) -> list[Image.Image]`

- Opens PDF bytes with PyMuPDF.
- Rejects a document when its page count exceeds `max_pages`.
- Renders every page as an RGB image at 150 DPI by default.
- Closes the PyMuPDF document deterministically.
- Rejects empty PDFs and invalid page/DPI limits.

#### `image_to_bytes(img) -> bytes`

Serializes a Pillow image as PNG.

#### `embed_pages(pages, batch_size=2) -> list[list[list[float]]]`

- Processes pages in batches of two.
- Produces a matrix of ColQwen2 patch/token vectors for each page.
- Moves returned vectors to CPU float values for serialization.
- Validates batch size and output count.

#### `embed_query_tokens(query) -> list[list[float]]`

Creates ColQwen2 query-token vectors for multimodal retrieval and rejects blank
queries.

#### `ingest_pdf_multimodal(file_bytes, document_id, max_pages=None)`

Returns:

```text
(page_embeddings, page_image_urls, page_count)
```

It renders pages, embeds them, uploads each PNG under
`pages/{document_id}/page_{number}.png`, and returns the uploaded URLs.

Capabilities:

- Preserves full-page visual layout, charts, tables, images, and scanned text.
- Stores multi-vector page embeddings in a dedicated Qdrant collection.
- Supports visual query embeddings for late-interaction page retrieval.
- Applies a configurable page-count safety limit.

Limitations:

- Only the dedicated `POST /ingest/multimodal` endpoint accepts it, and that
  endpoint only accepts PDFs.
- It indexes pages rather than text chunks.
- It requires configured object storage for page images.
- PyTorch and `colpali_engine` are intentionally absent from the default
  `requirements.txt`; this path needs a separate heavy runtime/profile. Both
  are imported only when model inference is requested.
- CPU execution is expected to be slow and memory-intensive.
- A partial image-upload failure is handled by endpoint cleanup, not by a
  transaction within this module.

## Shared tokenization

### `tokenize.py: split_sentences(text) -> list[str]`

The helper first calls `nltk.sent_tokenize()`. If required NLTK tokenizer data
is unavailable, it falls back to:

```regex
(?<=[.!?])\s+|\n+(?=\S)
```

The fallback prevents ingestion from failing solely because tokenizer data is
missing, but it is less accurate for abbreviations, decimals, and text without
conventional punctuation.

## Registry methods

`registry.py` is the catalog and validation boundary. It deliberately imports
chunker modules only when their callable is requested, keeping catalog listing
lightweight.

### `ChunkerDefinition.public_dict() -> dict`

Serializes public metadata while removing `callable_path` and `internal`.

### `ChunkerDefinition.load_callable() -> Callable`

Imports the configured module and resolves the function after splitting its
`module:function` path. It raises a type error if the configured target is not
callable.

### `list_chunkers(include_internal=False) -> list[dict]`

Returns public metadata in registry insertion order. This powers
`GET /chunkers`.

### `available_chunker_ids(include_internal=False) -> list[str]`

Returns selectable IDs in the same order.

### `get_chunker_definition(chunker_id) -> ChunkerDefinition`

Trims the ID, validates exact registry membership, and raises a `ValueError`
that lists the available IDs when invalid.

### `get_chunker(chunker_id) -> Callable`

Returns the lazily imported callable configured for the selected definition.

### `get_default_chunker() -> ChunkerDefinition`

Returns the first definition marked as default. The current default is
`paragraph`; the method raises when no default exists.

### `validate_chunker(chunker_id) -> str`

Validates an ID and returns its canonical registry value.

## Ingestion and indexing behavior

| Path | Behavior |
|---|---|
| `POST /ingest/file` | Validates a text chunker, lands the source in Bronze, and lets the Airflow Bronze-to-Silver job load the registered callable. |
| `POST /ingest/url` and `POST /ingest/gdrive` | Parse, chunk, embed, and index synchronously. Specialized hierarchical and late-chunking indexers are used. |
| `POST /ingest/multimodal` | Bypasses text chunking and performs page rendering, image upload, ColQwen2 embedding, and dedicated Qdrant indexing. |
| `GET /chunkers` | Returns all eight public registry definitions without callable paths. |

For regular text chunkers, Silver rows currently record `chunk_index`, text,
content hash, parser filename, and chunker ID. Token count, page range, and
section title are left unset. Consequently, none of the text strategies
currently preserves parser page or section lineage through this generic
artifact path.

The ingestion planner assigns resource hints from registry capabilities:

- `fixed_size`, `paragraph`, and `sentence`: CPU throughput profile, embedding
  batch size 192, maximum parallelism 4.
- `hierarchical`: structured CPU profile, batch size 96, maximum parallelism 2.
- `semantic` and `late_chunking`: high-memory CPU profile, batch size 48,
  maximum parallelism 1.
- `proposition`: network/LLM profile, batch size 32, maximum parallelism 1.
- `multimodal`: GPU profile, batch size 2, maximum parallelism 1.

These are execution hints exported to workers; the chunker functions
themselves do not enforce parallelism or resource isolation.

## Remaining implementation boundaries

The following differences are important when presenting chunker capabilities
to API or frontend users:

1. `hierarchical` groups fixed counts of sentences and does not inspect
   headings or sections. The asynchronous file pipeline also loses its
   parent/child metadata.
2. `late_chunking` mean-pools independently generated sentence embeddings; it
   does not create token embeddings from one full-document contextual forward
   pass.
3. `multimodal` is a separate PDF page ingestion workflow, not a drop-in text
   chunk function, and its heavy dependencies are optional.
4. Generic text artifact rows do not currently retain page, section, or parser
   lineage beyond the parser filename.
