from fastapi import APIRouter
from app.api.v1.endpoints.auth import login, register, roles, users
from app.api.v1.endpoints.hr import attendance, employees, holidays, salary, shifts
from app.api.v1.endpoints.inventory import analytics, categories, inventory_counts, items, reorder_requests, stock_levels, stock_movements, stock_types, transfers
from app.api.v1.endpoints.organization import departments, locations
from app.api.v1.endpoints.purchase import goods_receipts, purchase_orders, suppliers

api_router = APIRouter()

# Authentication routes
api_router.include_router(login.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(register.router, prefix="/register", tags=["Register"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])

# Main application routes
# Organization routes
api_router.include_router(departments.router, prefix="/organization/department", tags=["Organization"])
api_router.include_router(locations.router, prefix="/organization/location", tags=["Organization"])

# HR routes
api_router.include_router(employees.router, prefix="/hr/employee", tags=["Human Resource"])
api_router.include_router(shifts.router, prefix="/hr/shift", tags=["Human Resource"])
api_router.include_router(attendance.router, prefix="/hr/attendance", tags=["Human Resource"])
api_router.include_router(salary.router, prefix="/hr/salary", tags=["Human Resource"])
api_router.include_router(holidays.router, prefix="/hr/holiday", tags=["Human Resource"])

# Inventory routes
api_router.include_router(analytics.router, prefix="/inventory/analytics", tags=["Inventory"])
api_router.include_router(categories.router, prefix="/inventory/category", tags=["Inventory"])
api_router.include_router(inventory_counts.router, prefix="/inventory/inventory-count", tags=["Inventory"])
api_router.include_router(items.router, prefix="/inventory/item", tags=["Inventory"])
api_router.include_router(reorder_requests.router, prefix="/inventory/reorder-request", tags=["Inventory"])
api_router.include_router(stock_levels.router, prefix="/inventory/stock-level", tags=["Inventory"])
api_router.include_router(stock_movements.router, prefix="/inventory/stock-movement", tags=["Inventory"])
api_router.include_router(stock_types.router, prefix="/inventory/stock-type", tags=["Inventory"])
api_router.include_router(transfers.router, prefix="/inventory/transfer", tags=["Inventory"])

# Purchase routes
api_router.include_router(goods_receipts.router, prefix="/purchase/goods-receipt", tags=["Purchase"])
api_router.include_router(purchase_orders.router, prefix="/purchase/purchase-order", tags=["Purchase"])
api_router.include_router(suppliers.router, prefix="/purchase/suplier", tags=["Purchase"])