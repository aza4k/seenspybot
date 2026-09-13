from .common import router as common_router
from .business import router as business_router
from .payments import router as payments_router
from .admin import router as admin_router

__all__ = ["common_router", "business_router", "payments_router", "admin_router"]
