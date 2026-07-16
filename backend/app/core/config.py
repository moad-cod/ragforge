from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    QDRANT_URL: str
    QDRANT_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MAX_RETRIES: int = 2
    LLM_TIMEOUT_SECONDS: float = 60.0
    EMBEDDING_BACKEND: str = "fastembed"

    # Cloudflare R2 is needed only for multimodal PDF ingestion.
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_URL: str = ""

    # MinIO is the durable data lake for Bronze/Silver/Gold artifacts.
    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "ragforge"
    MINIO_SECRET_KEY: str = "ragforge123"
    MINIO_BUCKET_BRONZE: str = "bronze"
    MINIO_BUCKET_SILVER: str = "silver"
    MINIO_BUCKET_GOLD: str = "gold"

    # Redis is an optional query-response cache. PostgreSQL remains durable.
    REDIS_URL: str = ""
    QUERY_CACHE_TTL_SECONDS: int = 300
    EVENT_STREAM_MAXLEN: int = 512
    EVENT_STREAM_TTL_SECONDS: int = 3600
    SSE_HEARTBEAT_SECONDS: float = 15.0
    SSE_POLL_SECONDS: float = 1.0

    # Optional Airflow REST trigger. Landed runs remain durable when disabled.
    AIRFLOW_API_URL: str = ""
    AIRFLOW_USERNAME: str = "admin"
    AIRFLOW_PASSWORD: str = "admin"
    AIRFLOW_INGESTION_DAG_ID: str = "ragforge_ingestion"
    PIPELINE_SERVICE_TOKEN: str = ""

    DEBUG_RETURN_CONTEXT: bool = False
    MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    MAX_MULTIMODAL_PAGES: int = 50

    class Config:
        env_file = ".env"
        extra = "ignore"

    def require_llm_provider(self, provider: str) -> None:
        if provider == "gemini" and not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required for Gemini queries")
        if provider == "groq" and not self.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is required for Groq queries")

    def require_r2(self) -> None:
        missing = [
            name for name in (
                "R2_ACCOUNT_ID",
                "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY",
                "R2_BUCKET_NAME",
                "R2_PUBLIC_URL",
            )
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"Missing R2 settings: {', '.join(missing)}")

    @property
    def minio_endpoint_url(self) -> str:
        endpoint = self.MINIO_ENDPOINT.rstrip("/")
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"
        return endpoint

settings = Settings()
