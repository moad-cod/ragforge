from dataclasses import asdict, dataclass, field
from importlib import import_module
from typing import Callable


@dataclass(frozen=True)
class ChunkerDefinition:
    id: str
    name: str
    tier: str
    status: str
    is_beta: bool
    short_description: str
    long_description: str
    best_for: list[str]
    not_recommended_for: list[str]
    speed_level: str
    quality_level: str
    cost_level: str
    requires_llm: bool
    requires_nltk: bool
    requires_embedding_model: bool
    requires_multimodal: bool
    default: bool
    callable_path: str = field(repr=False)
    internal: bool = field(default=False, repr=False)

    def public_dict(self) -> dict:
        data = asdict(self)
        data.pop("callable_path", None)
        data.pop("internal", None)
        return data

    def load_callable(self) -> Callable:
        module_path, function_name = self.callable_path.split(":", 1)
        value = getattr(import_module(module_path), function_name)
        if not callable(value):
            raise TypeError(f"Configured chunker target {self.callable_path!r} is not callable")
        return value


CHUNKER_REGISTRY: dict[str, ChunkerDefinition] = {
    "fixed_size": ChunkerDefinition(
        id="fixed_size",
        name="Starter Chunking",
        tier="base",
        status="stable",
        is_beta=False,
        short_description="Simple fixed-size chunking for fast and predictable ingestion.",
        long_description="Starter Chunking splits documents into consistent fixed-size text blocks. It is optimized for speed, simplicity, and predictable indexing behavior. This mode is useful for early testing, simple documents, and low-cost ingestion pipelines where advanced semantic structure is not required.",
        best_for=["quick testing", "simple text files", "predictable chunk sizes", "low-cost ingestion", "baseline retrieval experiments"],
        not_recommended_for=["complex documents", "documents with important section structure", "legal, compliance, or technical content requiring precision"],
        speed_level="fast",
        quality_level="basic",
        cost_level="low",
        requires_llm=False,
        requires_nltk=False,
        requires_embedding_model=False,
        requires_multimodal=False,
        default=False,
        callable_path="app.services.chunkers.fixed_size:chunk",
    ),
    "paragraph": ChunkerDefinition(
        id="paragraph",
        name="Base Chunking",
        tier="base",
        status="stable",
        is_beta=False,
        short_description="Fast, reliable chunking for clean documents with natural paragraph structure.",
        long_description="Base Chunking packs natural paragraphs into bounded chunks and splits only oversized paragraphs into overlapping word windows. It is ideal for general PDFs, markdown files, articles, reports, and documentation where the text is already well structured. This is the recommended default for most users because it is stable, lightweight, and cost-efficient.",
        best_for=["general documents", "documentation", "markdown files", "articles", "reports", "fast ingestion", "low-cost indexing"],
        not_recommended_for=["very dense legal or academic text", "documents with poor formatting", "cases requiring maximum semantic precision"],
        speed_level="fast",
        quality_level="standard",
        cost_level="low",
        requires_llm=False,
        requires_nltk=False,
        requires_embedding_model=False,
        requires_multimodal=False,
        default=True,
        callable_path="app.services.chunkers.paragraph:chunk",
    ),
    "sentence": ChunkerDefinition(
        id="sentence",
        name="Precision Chunking",
        tier="pro",
        status="stable",
        is_beta=False,
        short_description="More precise chunking for dense documents where sentence boundaries matter.",
        long_description="Precision Chunking creates cleaner retrieval units by respecting sentence boundaries and merging very short fragments rather than discarding them. It is designed for dense text, policies, manuals, educational content, and knowledge-base documents where paragraph splitting may create chunks that are too broad or inconsistent. It uses NLTK when tokenizer data is available and an offline regex fallback otherwise.",
        best_for=["dense text", "policies", "manuals", "educational documents", "knowledge bases", "documents with long paragraphs"],
        not_recommended_for=["extremely large files where speed is the top priority", "environments where tokenizer data is unavailable"],
        speed_level="medium",
        quality_level="high",
        cost_level="low",
        requires_llm=False,
        requires_nltk=True,
        requires_embedding_model=False,
        requires_multimodal=False,
        default=False,
        callable_path="app.services.chunkers.sentence:chunk",
    ),
    "semantic": ChunkerDefinition(
        id="semantic",
        name="Semantic Chunking",
        tier="pro",
        status="beta",
        is_beta=True,
        short_description="Embedding-aware chunking that groups text by semantic meaning.",
        long_description="Semantic Chunking uses meaning-aware boundaries to create chunks that better match how users ask questions. Instead of relying only on paragraphs or sentences, it attempts to keep related ideas together and separate topic shifts. This mode is designed for teams that need better retrieval quality on dense or inconsistent documents while keeping ingestion more affordable than full LLM-based proposition extraction.",
        best_for=["dense business documents", "research notes", "technical documentation", "documents with inconsistent formatting", "higher-quality retrieval without full LLM processing"],
        not_recommended_for=["very large bulk ingestion when speed is critical", "environments where local embedding models are unavailable", "simple documents where paragraph chunking is enough"],
        speed_level="medium",
        quality_level="high",
        cost_level="medium",
        requires_llm=False,
        requires_nltk=True,
        requires_embedding_model=True,
        requires_multimodal=False,
        default=False,
        callable_path="app.services.chunkers.semantic:chunk",
    ),
    "hierarchical": ChunkerDefinition(
        id="hierarchical",
        name="Structured Chunking",
        tier="business",
        status="beta",
        is_beta=True,
        short_description="Structure-aware chunking for documents with headings, sections, and nested content.",
        long_description="Structured Chunking is designed for long-form documents that contain headings, sections, subsections, and layered information. It preserves document hierarchy so retrieved context can remain connected to the original structure. This is useful for manuals, policies, technical documentation, and enterprise knowledge bases where section-level context matters.",
        best_for=["manuals", "policy documents", "technical documentation", "structured reports", "enterprise knowledge bases", "documents with headings and sections"],
        not_recommended_for=["plain unstructured text", "short documents", "messy OCR text with no clear structure"],
        speed_level="medium",
        quality_level="high",
        cost_level="medium",
        requires_llm=False,
        requires_nltk=True,
        requires_embedding_model=False,
        requires_multimodal=False,
        default=False,
        callable_path="app.services.chunkers.hierarchical:chunk",
    ),
    "late_chunking": ChunkerDefinition(
        id="late_chunking",
        name="Late Interaction Chunking",
        tier="ultimate",
        status="beta",
        is_beta=True,
        short_description="Advanced embedding-first chunking for premium retrieval quality.",
        long_description="Late Interaction Chunking is an advanced retrieval optimization mode that uses model-aware processing to improve chunk boundaries after understanding broader document context. It is designed for premium RAG workflows where answer quality, context preservation, and retrieval accuracy matter more than ingestion speed. This mode is best suited for complex documents and evaluation-focused teams.",
        best_for=["premium RAG workflows", "complex documents", "evaluation-focused experiments", "technical and legal-style content", "accuracy-sensitive retrieval"],
        not_recommended_for=["fast bulk ingestion", "low-cost indexing", "small/simple documents", "lightweight development environments"],
        speed_level="slow",
        quality_level="premium",
        cost_level="high",
        requires_llm=False,
        requires_nltk=True,
        requires_embedding_model=True,
        requires_multimodal=False,
        default=False,
        callable_path="app.services.chunkers.late_chunking:chunk",
    ),
    "proposition": ChunkerDefinition(
        id="proposition",
        name="Ultimate Chunking",
        tier="ultimate",
        status="beta",
        is_beta=True,
        short_description="Advanced semantic proposition extraction designed for higher-accuracy RAG answers.",
        long_description="Ultimate Chunking extracts smaller, meaning-focused propositions from source documents. It is designed for teams that care about answer accuracy, factual grounding, and retrieval quality. This mode can improve performance on complex documents by turning long passages into precise knowledge units. Because it may use LLM-based processing and is more expensive, it should be presented as a beta or premium option.",
        best_for=["high-accuracy RAG", "complex business documents", "legal-style documents", "technical documentation", "compliance content", "evaluation-focused workflows", "premium SaaS users"],
        not_recommended_for=["low-cost bulk ingestion", "very large document batches", "real-time ingestion", "users who need the fastest indexing speed"],
        speed_level="slow",
        quality_level="premium",
        cost_level="high",
        requires_llm=True,
        requires_nltk=False,
        requires_embedding_model=False,
        requires_multimodal=False,
        default=False,
        callable_path="app.services.chunkers.proposition:chunk",
    ),
    "multimodal": ChunkerDefinition(
        id="multimodal",
        name="Multimodal Chunking",
        tier="ultimate",
        status="experimental",
        is_beta=True,
        short_description="Experimental visual-document chunking for PDFs with pages, images, charts, and layouts.",
        long_description="Multimodal Chunking is designed for documents where visual layout matters, such as slide decks, scanned PDFs, charts, tables, screenshots, and image-heavy reports. It can preserve page-level visual context and connect text with visual evidence. This mode is experimental and should be used for advanced workflows where users need retrieval over both text and document visuals.",
        best_for=["scanned PDFs", "visual reports", "charts and tables", "slide decks", "image-heavy documents", "multimodal RAG experiments"],
        not_recommended_for=["simple text documents", "low-cost ingestion", "very large PDFs without page limits", "production workflows that require maximum stability"],
        speed_level="slow",
        quality_level="premium",
        cost_level="high",
        requires_llm=False,
        requires_nltk=False,
        requires_embedding_model=True,
        requires_multimodal=True,
        default=False,
        callable_path="app.services.chunkers.multimodal:ingest_pdf_multimodal",
    ),
}


def list_chunkers(include_internal: bool = False) -> list[dict]:
    return [
        chunker.public_dict()
        for chunker in CHUNKER_REGISTRY.values()
        if include_internal or not chunker.internal
    ]


def available_chunker_ids(include_internal: bool = False) -> list[str]:
    return [
        chunker.id
        for chunker in CHUNKER_REGISTRY.values()
        if include_internal or not chunker.internal
    ]


def get_chunker_definition(chunker_id: str) -> ChunkerDefinition:
    chunker_id = (chunker_id or "").strip()
    if chunker_id not in CHUNKER_REGISTRY:
        available = ", ".join(available_chunker_ids())
        raise ValueError(f"Invalid chunker '{chunker_id}'. Available chunkers: {available}.")
    return CHUNKER_REGISTRY[chunker_id]


def get_chunker(chunker_id: str) -> Callable:
    return get_chunker_definition(chunker_id).load_callable()


def get_default_chunker() -> ChunkerDefinition:
    for chunker in CHUNKER_REGISTRY.values():
        if chunker.default:
            return chunker
    raise RuntimeError("No default chunker configured")


def validate_chunker(chunker_id: str) -> str:
    return get_chunker_definition(chunker_id).id
