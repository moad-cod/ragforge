from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    QDRANT_URL: str
    QDRANT_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # Cloudflare R2 is needed only for multimodal PDF ingestion.
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_URL: str = ""

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

settings = Settings()
