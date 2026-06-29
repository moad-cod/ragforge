from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    QDRANT_URL: str
    QDRANT_API_KEY: str = ""
    GEMINI_API_KEY: str
    GROQ_API_KEY: str

    class Config:
        env_file = ".env"
        extra = "ignore"    # ← ignores QDRANT_COLLECTION and any other unknown keys

settings = Settings()