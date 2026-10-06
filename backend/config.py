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

    # Amazon PA-API / Creators API Credentials
    AMAZON_ACCESS_KEY: str = os.getenv("AMAZON_ACCESS_KEY", "")
    AMAZON_SECRET_KEY: str = os.getenv("AMAZON_SECRET_KEY", "")
    AMAZON_ASSOCIATE_TAG: str = os.getenv("AMAZON_ASSOCIATE_TAG", "")
    AMAZON_HOST: str = os.getenv("AMAZON_HOST", "webservices.amazon.in")
    AMAZON_REGION: str = os.getenv("AMAZON_REGION", "eu-west-1")
    AMAZON_CREATOR_TOKEN: str = os.getenv("AMAZON_CREATOR_TOKEN", "")

    # Flipkart Affiliate API Credentials
    FLIPKART_AFFILIATE_ID: str = os.getenv("FLIPKART_AFFILIATE_ID", "")
    FLIPKART_AFFILIATE_TOKEN: str = os.getenv("FLIPKART_AFFILIATE_TOKEN", "")

    # Bing Search API Credentials
    BING_SEARCH_API_KEY: str = os.getenv("BING_SEARCH_API_KEY", "")

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
