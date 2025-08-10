from fastapi import APIRouter
from app.api.v1.endpoints import (
    # inventory,
    # hr,
    # purchase,
    # logistics,
    # dashboard,
    # reports,
    ai_chat
)
# from app.api.v1.auth import login, users, roles

api_router = APIRouter()

# Authentication routes
# api_router.include_router(login.router, prefix="/auth", tags=["Authentication"])
# api_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])

# Main application routes
# api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
# api_router.include_router(hr.router, prefix="/hr", tags=["Human Resources"])
# api_router.include_router(purchase.router, prefix="/purchase", tags=["Purchase"])
# api_router.include_router(logistics.router, prefix="/logistics", tags=["Logistics"])
# api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
# api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
# api_router.include_router(ai_chat.router, prefix="/ai", tags=["AI Chat"])