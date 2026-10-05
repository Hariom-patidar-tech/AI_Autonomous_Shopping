from fastapi import APIRouter
from backend.config import settings
from backend.database import engine

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    db_status = "connected"
    try:
        with engine.connect() as conn:
            pass
    except Exception:
        db_status = "fallback_or_degraded"

    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "database": db_status,
        "search_provider": settings.SEARCH_PROVIDER,
    }
