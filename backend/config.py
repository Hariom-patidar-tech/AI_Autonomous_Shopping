import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    APP_NAME: str = "Universal AI Shopping & Price Comparison Agent"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = os.getenv("APP_ENV", "production")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # LLM & Search Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    SEARCH_PROVIDER: str = os.getenv("SEARCH_PROVIDER", "google")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:mypostgresql@localhost:5432/shopping_agent"
    )
    FALLBACK_SQLITE_URL: str = os.getenv(
        "FALLBACK_SQLITE_URL",
        f"sqlite:///{BASE_DIR}/shopping_agent.db"
    )

    # Search Limits
    MAX_CANDIDATES: int = 15
    MAX_SEARCH_RESULTS: int = 10
    REQUEST_TIMEOUT_SECONDS: float = 15.0

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Settings()
