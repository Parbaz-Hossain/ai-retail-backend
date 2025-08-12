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

ROLES_SEED = [
    {"name": "super_admin",      "description": "Full system access",               "is_system_role": True},
    {"name": "admin",            "description": "System administrator",             "is_system_role": True},
    {"name": "store_manager",    "description": "Store Manager",                    "is_system_role": False},
    {"name": "inventory_manager","description": "Inventory Manager",                "is_system_role": False},
    {"name": "hr_manager",       "description": "HR Manager",                       "is_system_role": False},
    {"name": "logistics_manager","description": "Logistics Manager",                "is_system_role": False},
    {"name": "cashier",          "description": "Cashier",                          "is_system_role": False},
    {"name": "employee",         "description": "Employee",                         "is_system_role": False},
    {"name": "driver",           "description": "Delivery Driver",                  "is_system_role": False},
    {"name": "auditor",          "description": "Auditor (read-only)",              "is_system_role": False},
]

USERS_SEED = [
    {
        "email": "superadmin@blumencafe.com",
        "username": "superadmin",
        "full_name": "Super Administrator",
        "hashed_password": get_password_hash("SuperAdmin123!"),
        "is_superuser": True, "is_verified": True,
        "phone": "+8801712345001", "address": "Blumen Cafe HQ, Dhaka, Bangladesh"
    },
    {
        "email": "admin@blumencafe.com",
        "username": "admin",
        "full_name": "System Administrator",
        "hashed_password": get_password_hash("Admin123!"),
        "is_superuser": False, "is_verified": True,
        "phone": "+8801712345002", "address": "Blumen Cafe Main Office, Dhaka"
    },
    {
        "email": "manager@blumencafe.com",
        "username": "store_manager",
        "full_name": "Ahmed Rahman",
        "hashed_password": get_password_hash("Manager123!"),
        "is_superuser": False, "is_verified": True,
        "phone": "+8801712345003", "address": "Gulshan Store, Dhaka"
    },
    {
        "email": "inventory@blumencafe.com",
        "username": "inv_manager",
        "full_name": "Fatima Khan",
        "hashed_password": get_password_hash("Inventory123!"),
        "is_superuser": False, "is_verified": True,
        "phone": "+8801712345004", "address": "Warehouse, Savar, Dhaka"
    },
    {
        "email": "hr@blumencafe.com",
        "username": "hr_manager",
        "full_name": "Mohammad Ali",
        "hashed_password": get_password_hash("HrManager123!"),
        "is_superuser": False, "is_verified": True,
        "phone": "+8801712345005", "address": "HR Department, Main Office"
    },
    {
        "email": "logistics@blumencafe.com",
        "username": "logistics_mgr",
        "full_name": "Rashida Begum",
        "hashed_password": get_password_hash("Logistics123!"),
        "is_superuser": False, "is_verified": True,
        "phone": "+8801712345006", "address": "Logistics Center, Dhaka"
    },
    {
        "email": "cashier1@blumencafe.com",
        "username": "cashier1",
        "full_name": "Sadia Islam",
        "hashed_password": get_password_hash("Cashier123!"),
        "is_superuser": False, "is_verified": True,
        "phone": "+8801712345007", "address": "Dhanmondi Branch, Dhaka"
    },
    {
        "email": "employee1@blumencafe.com",
        "username": "employee1",
        "full_name": "Karim Uddin",
        "hashed_password": get_password_hash("Employee123!"),
        "is_superuser": False, "is_verified": True,
        "phone": "+8801712345008", "address": "Uttara Branch, Dhaka"
    },
    {
        "email": "driver1@blumencafe.com",
        "username": "driver1",
        "full_name": "Abdul Jabbar",
        "hashed_password": get_password_hash("Driver123!"),
        "is_superuser": False, "is_verified": True,
        "phone": "+8801712345009", "address": "Delivery Department, Dhaka"
    },
    {
        "email": "auditor@blumencafe.com",
        "username": "auditor",
        "full_name": "Nasir Ahmed",
        "hashed_password": get_password_hash("Auditor123!"),
        "is_superuser": False, "is_verified": True,
        "phone": "+8801712345010", "address": "Audit Department, Main Office"
    },
]

ROLE_PERMISSIONS_MAPPING = {
    "super_admin": [p["name"] for p in PERMISSIONS_SEED],
    "admin": [
        "user:create","user:read","user:update",
        "role:read","role:update",
        "inventory:create","inventory:read","inventory:update","inventory:delete",
        "stock:create","stock:read","stock:update","stock:transfer",
        "purchase:create","purchase:read","purchase:update","purchase:approve","purchase:cancel",
        "hr:create","hr:read","hr:update","hr:salary",
        "attendance:read","attendance:update","attendance:manage",
        "shipment:create","shipment:read","shipment:update","shipment:cancel",
        "reports:read","reports:export","reports:create",
        "ai:interact","ai:configure",
        "department:create","department:read","department:update",
        "location:create","location:read","location:update",
        "supplier:create","supplier:read","supplier:update","supplier:delete",
        "system:configure"
    ],
    "store_manager": [
        "user:read","user:update",
        "inventory:read","inventory:update",
        "stock:read","stock:update","stock:transfer",
        "purchase:create","purchase:read","purchase:update",
        "hr:read","hr:update",
        "attendance:read","attendance:update",
        "shipment:create","shipment:read","shipment:update",
        "reports:read","reports:export",
        "ai:interact","department:read","location:read"
    ],
    "inventory_manager": [
        "inventory:create","inventory:read","inventory:update","inventory:delete",
        "stock:create","stock:read","stock:update","stock:transfer",
        "purchase:create","purchase:read","purchase:update","purchase:approve",
        "supplier:create","supplier:read","supplier:update",
        "reports:read","reports:export","ai:interact","location:read"
    ],
    "hr_manager": [
        "user:read","user:update",
        "hr:create","hr:read","hr:update","hr:delete","hr:salary",
        "attendance:read","attendance:update","attendance:manage",
        "reports:read","reports:export","ai:interact",
        "department:create","department:read","department:update"
    ],
    "logistics_manager": [
        "shipment:create","shipment:read","shipment:update","shipment:cancel",
        "stock:read","stock:transfer","reports:read","reports:export","ai:interact","location:read"
    ],
    "cashier": ["inventory:read","stock:read","reports:read","ai:interact"],
    "employee": ["user:read","attendance:read","ai:interact"],
    "driver": ["shipment:read","shipment:update","ai:interact"],
    "auditor": [
        "user:read","inventory:read","stock:read","purchase:read","hr:read","attendance:read",
        "shipment:read","reports:read","reports:export","department:read","location:read","supplier:read"
    ],
}

USER_ROLES_MAPPING = {
    "superadmin": ["super_admin"],
    "admin": ["admin"],
    "store_manager": ["store_manager"],
    "inv_manager": ["inventory_manager"],
    "hr_manager": ["hr_manager"],
    "logistics_mgr": ["logistics_manager"],
    "cashier1": ["cashier"],
    "employee1": ["employee"],
    "driver1": ["driver"],
    "auditor": ["auditor"],
}

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

async def get_or_create_role(db: AsyncSession, data: dict) -> Role:
    result = await db.execute(select(Role).where(Role.name == data["name"]))
    obj = result.scalar_one_or_none()
    if obj:
        return obj
    obj = Role(**data)
    db.add(obj)
    await db.flush()
    return obj

async def get_or_create_user(db: AsyncSession, data: dict) -> User:
    result = await db.execute(select(User).where(User.username == data["username"]))
    obj = result.scalar_one_or_none()
    if obj:
        return obj
    obj = User(**data)
    db.add(obj)
    await db.flush()
    return obj

async def link_role_perm(db: AsyncSession, role_id: int, perm_id: int):
    result = await db.execute(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == perm_id
        )
    )
    exists = result.scalar_one_or_none()
    if not exists:
        db.add(RolePermission(role_id=role_id, permission_id=perm_id))

async def link_user_role(db: AsyncSession, user_id: int, role_id: int, assigned_by_id: int | None = None):
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id
        )
    )
    exists = result.scalar_one_or_none()
    if not exists:
        db.add(UserRole(user_id=user_id, role_id=role_id, assigned_by=assigned_by_id))

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

    # 2) Ensure roles
    role_objs = {}
    for r in ROLES_SEED:
        role = await get_or_create_role(db, r)
        role_objs[r["name"]] = role
    await db.commit()
    print(f"✓ Roles ready: {len(role_objs)}")

    # 3) Map role → permissions
    for role_name, perm_names in ROLE_PERMISSIONS_MAPPING.items():
        role = role_objs.get(role_name)
        if not role:
            continue
        for pname in perm_names:
            perm = perm_objs.get(pname)
            if perm:
                await link_role_perm(db, role.id, perm.id)
    await db.commit()
    print("✓ Role permissions mapped")

    # 4) Ensure users
    user_objs = {}
    for u in USERS_SEED:
        user = await get_or_create_user(db, u)
        user_objs[u["username"]] = user
    await db.commit()
    print(f"✓ Users ready: {len(user_objs)}")

    # 5) Map user → roles (assigned_by = superadmin if exists)
    assigned_by = user_objs.get("superadmin").id if "superadmin" in user_objs else None
    for username, roles in USER_ROLES_MAPPING.items():
        user = user_objs.get(username)
        if not user:
            continue
        for rname in roles:
            role = role_objs.get(rname)
            if role:
                await link_user_role(db, user.id, role.id, assigned_by)
    await db.commit()
    print("✓ User roles mapped")

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