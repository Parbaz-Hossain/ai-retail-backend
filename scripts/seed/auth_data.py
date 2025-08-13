"""
Authentication Models Seed Data (async, idempotent)
- Permissions, Roles, Users
- RolePermission and UserRole mappings
Run:  python scripts/seed/seed_auth.py
"""

import os, sys
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_maker, engine
from app.models.base import Base
from app.models.auth.permission import Permission
from app.models.auth.role import Role
from app.models.auth.role_permission import RolePermission
from app.models.auth.user import User
from app.models.auth.user_role import UserRole
from app.core.security import get_password_hash

# ----------------------------------------------------------------------
# SEED DATA
# ----------------------------------------------------------------------

PERMISSIONS_SEED = [
    # User Management
    {"name": "user:create", "description": "Create new users", "resource": "user", "action": "create"},
    {"name": "user:read",   "description": "Read user information", "resource": "user", "action": "read"},
    {"name": "user:update", "description": "Update user information", "resource": "user", "action": "update"},
    {"name": "user:delete", "description": "Delete users", "resource": "user", "action": "delete"},

    # Role Management
    {"name": "role:create", "description": "Create new roles", "resource": "role", "action": "create"},
    {"name": "role:read",   "description": "Read role information", "resource": "role", "action": "read"},
    {"name": "role:update", "description": "Update role information", "resource": "role", "action": "update"},
    {"name": "role:delete", "description": "Delete roles", "resource": "role", "action": "delete"},

    # Inventory
    {"name": "inventory:create", "description": "Create inventory items", "resource": "inventory", "action": "create"},
    {"name": "inventory:read",   "description": "View inventory items",   "resource": "inventory", "action": "read"},
    {"name": "inventory:update", "description": "Update inventory items", "resource": "inventory", "action": "update"},
    {"name": "inventory:delete", "description": "Delete inventory items", "resource": "inventory", "action": "delete"},

    # Stock
    {"name": "stock:create",   "description": "Create stock entries", "resource": "stock", "action": "create"},
    {"name": "stock:read",     "description": "View stock levels",    "resource": "stock", "action": "read"},
    {"name": "stock:update",   "description": "Update stock levels",  "resource": "stock", "action": "update"},
    {"name": "stock:transfer", "description": "Transfer stock",       "resource": "stock", "action": "transfer"},

    # Purchase
    {"name": "purchase:create",  "description": "Create POs", "resource": "purchase", "action": "create"},
    {"name": "purchase:read",    "description": "View POs",   "resource": "purchase", "action": "read"},
    {"name": "purchase:update",  "description": "Update POs", "resource": "purchase", "action": "update"},
    {"name": "purchase:approve", "description": "Approve POs","resource": "purchase", "action": "approve"},
    {"name": "purchase:cancel",  "description": "Cancel POs", "resource": "purchase", "action": "cancel"},

    # HR
    {"name": "hr:create",  "description": "Create employees", "resource": "hr", "action": "create"},
    {"name": "hr:read",    "description": "View employees",    "resource": "hr", "action": "read"},
    {"name": "hr:update",  "description": "Update employees",  "resource": "hr", "action": "update"},
    {"name": "hr:delete",  "description": "Delete employees",  "resource": "hr", "action": "delete"},
    {"name": "hr:salary",  "description": "Manage salaries",   "resource": "hr", "action": "salary"},

    # Attendance
    {"name": "attendance:read",    "description": "View attendance",   "resource": "attendance", "action": "read"},
    {"name": "attendance:update",  "description": "Update attendance", "resource": "attendance", "action": "update"},
    {"name": "attendance:manage",  "description": "Manage attendance", "resource": "attendance", "action": "manage"},

    # Shipment
    {"name": "shipment:create", "description": "Create shipments", "resource": "shipment", "action": "create"},
    {"name": "shipment:read",   "description": "View shipments",   "resource": "shipment", "action": "read"},
    {"name": "shipment:update", "description": "Update shipments", "resource": "shipment", "action": "update"},
    {"name": "shipment:cancel", "description": "Cancel shipments", "resource": "shipment", "action": "cancel"},

    # Reports
    {"name": "reports:read",   "description": "View reports",  "resource": "reports", "action": "read"},
    {"name": "reports:export", "description": "Export reports","resource": "reports", "action": "export"},
    {"name": "reports:create", "description": "Create reports","resource": "reports", "action": "create"},

    # AI
    {"name": "ai:interact",   "description": "Interact with AI",    "resource": "ai", "action": "interact"},
    {"name": "ai:configure",  "description": "Configure AI",         "resource": "ai", "action": "configure"},
    {"name": "ai:train",      "description": "Train AI models",      "resource": "ai", "action": "train"},

    # Department
    {"name": "department:create", "description": "Create departments", "resource": "department", "action": "create"},
    {"name": "department:read",   "description": "View departments",   "resource": "department", "action": "read"},
    {"name": "department:update", "description": "Update departments", "resource": "department", "action": "update"},
    {"name": "department:delete", "description": "Delete departments", "resource": "department", "action": "delete"},

    # Location
    {"name": "location:create", "description": "Create locations", "resource": "location", "action": "create"},
    {"name": "location:read",   "description": "View locations",   "resource": "location", "action": "read"},
    {"name": "location:update", "description": "Update locations", "resource": "location", "action": "update"},
    {"name": "location:delete", "description": "Delete locations", "resource": "location", "action": "delete"},

    # Supplier
    {"name": "supplier:create", "description": "Create suppliers", "resource": "supplier", "action": "create"},
    {"name": "supplier:read",   "description": "View suppliers",   "resource": "supplier", "action": "read"},
    {"name": "supplier:update", "description": "Update suppliers", "resource": "supplier", "action": "update"},
    {"name": "supplier:delete", "description": "Delete suppliers", "resource": "supplier", "action": "delete"},

    # System
    {"name": "system:admin",     "description": "System admin",     "resource": "system", "action": "admin"},
    {"name": "system:backup",    "description": "Backup & restore", "resource": "system", "action": "backup"},
    {"name": "system:configure", "description": "System config",    "resource": "system", "action": "configure"},
]

# ----------------------------------------------------------------------
# ASYNC HELPERS (idempotent upserts)
# ----------------------------------------------------------------------

async def get_or_create_permission(db: AsyncSession, data: dict) -> Permission:
    result = await db.execute(select(Permission).where(Permission.name == data["name"]))
    obj = result.scalar_one_or_none()
    if obj:
        return obj
    obj = Permission(**data)
    db.add(obj)
    await db.flush()
    return obj

# ----------------------------------------------------------------------
# MAIN ASYNC SEED LOGIC
# ----------------------------------------------------------------------

async def seed(db: AsyncSession):
    # 1) Ensure permissions
    perm_objs = {}
    for p in PERMISSIONS_SEED:
        perm = await get_or_create_permission(db, p)
        perm_objs[p["name"]] = perm
    await db.commit()
    print(f"✓ Permissions ready: {len(perm_objs)}")

# ----------------------------------------------------------------------
# ASYNC ENTRY POINT
# ----------------------------------------------------------------------

async def main():
    # Create tables (safe if already created)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as db:
        try:
            await seed(db)
            print("✅ Authentication seed completed successfully!")
        except Exception as ex:
            await db.rollback()
            print(f"❌ Seed failed: {ex}")
            raise

if __name__ == "__main__":
    asyncio.run(main())