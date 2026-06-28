from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    QDRANT_URL: str
    QDRANT_COLLECTION: str = "ragforge_docs"
    GROQ_API_KEY: str
    GEMINI_API_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()