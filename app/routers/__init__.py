from app.routers.admin_items import router as admin_items_router
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.inventory import router as inventory_router
from app.routers.items import router as items_router
from app.routers.purchases import router as purchases_router
from app.routers.refunds import router as refunds_router
from app.routers.wallet import router as wallet_router

__all__ = [
    "admin_items_router",
    "auth_router",
    "health_router",
    "inventory_router",
    "items_router",
    "purchases_router",
    "refunds_router",
    "wallet_router",
]
