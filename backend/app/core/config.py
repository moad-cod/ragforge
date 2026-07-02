from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    QDRANT_URL: str
    QDRANT_API_KEY: str = ""
    GEMINI_API_KEY: str
    GROQ_API_KEY: str

    # ── Cloudflare R2 ─────────────────────────────────────────────────────────
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    R2_PUBLIC_URL: str

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()