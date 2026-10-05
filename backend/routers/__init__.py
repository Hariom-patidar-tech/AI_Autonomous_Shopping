from backend.routers.health import router as health_router
from backend.routers.products import router as products_router
from backend.routers.comparison import router as comparison_router
from backend.routers.reviews import router as reviews_router
from backend.routers.cart import router as cart_router
from backend.routers.history import router as history_router
from backend.routers.agent import router as agent_router

__all__ = [
    "health_router",
    "products_router",
    "comparison_router",
    "reviews_router",
    "cart_router",
    "history_router",
    "agent_router",
]
