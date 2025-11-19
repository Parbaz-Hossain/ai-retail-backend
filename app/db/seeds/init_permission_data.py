"""
Authentication Models Seed Data (async, idempotent)
- Permissions, Roles, Users
- RolePermission and UserRole mappings
Run:  python scripts/seed/seed_auth.py
"""

import os, sys
import asyncio
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, project_root)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_maker, engine
from app.models.base import Base
from app.models.auth.permission import Permission

# ----------------------------------------------------------------------
# SEED DATA
# ----------------------------------------------------------------------

PERMISSIONS_SEED = [
    # ==================== DASHBOARD ====================
    {"name": "dashboard:view", "description": "View dashboard", "resource": "dashboard", "action": "view"},

    # ==================== USER MANAGEMENT ====================
    # {"name": "user:create", "description": "Create new users", "resource": "user", "action": "create"},
    # {"name": "user:read", "description": "Read user information", "resource": "user", "action": "read"},
    # {"name": "user:update", "description": "Update user information", "resource": "user", "action": "update"},
    # {"name": "user:delete", "description": "Delete users", "resource": "user", "action": "delete"},
    # {"name": "user:activate", "description": "Activate/Deactivate users", "resource": "user", "action": "activate"},
    # {"name": "user:export", "description": "Export user data", "resource": "user", "action": "export"},

    # Role Management
    # {"name": "role:create", "description": "Create new roles", "resource": "role", "action": "create"},
    # {"name": "role:read", "description": "Read role information", "resource": "role", "action": "read"},
    # {"name": "role:update", "description": "Update role information", "resource": "role", "action": "update"},
    # {"name": "role:delete", "description": "Delete roles", "resource": "role", "action": "delete"},
    # {"name": "role:assign", "description": "Assign roles to users", "resource": "role", "action": "assign"},
    # {"name": "role:export", "description": "Export role data", "resource": "role", "action": "export"},

    # Permission Management
    # {"name": "permission:create", "description": "Create permissions", "resource": "permission", "action": "create"},
    # {"name": "permission:read", "description": "View permissions", "resource": "permission", "action": "read"},
    # {"name": "permission:update", "description": "Update permissions", "resource": "permission", "action": "update"},
    # {"name": "permission:delete", "description": "Delete permissions", "resource": "permission", "action": "delete"},
    # {"name": "permission:assign", "description": "Assign permissions to roles", "resource": "permission", "action": "assign"},
    # {"name": "permission:export", "description": "Export permission data", "resource": "permission", "action": "export"},

    # ==================== APPROVAL ====================
    # Approval Settings
    {"name": "approval_settings:create", "description": "Create approval settings", "resource": "approval_settings", "action": "create"},
    {"name": "approval_settings:read", "description": "View approval settings", "resource": "approval_settings", "action": "read"},
    {"name": "approval_settings:update", "description": "Update approval settings", "resource": "approval_settings", "action": "update"},
    {"name": "approval_settings:delete", "description": "Delete approval settings", "resource": "approval_settings", "action": "delete"},
    {"name": "approval_settings:export", "description": "Export approval settings", "resource": "approval_settings", "action": "export"},

    # Approval Members
    {"name": "approval_member:create", "description": "Add approval members", "resource": "approval_member", "action": "create"},
    {"name": "approval_member:read", "description": "View approval members", "resource": "approval_member", "action": "read"},
    {"name": "approval_member:update", "description": "Update approval members", "resource": "approval_member", "action": "update"},
    {"name": "approval_member:delete", "description": "Remove approval members", "resource": "approval_member", "action": "delete"},
    {"name": "approval_member:export", "description": "Export approval members", "resource": "approval_member", "action": "export"},

    # Approval Requests
    {"name": "approval_request:create", "description": "Create approval requests", "resource": "approval_request", "action": "create"},
    {"name": "approval_request:read", "description": "View approval requests", "resource": "approval_request", "action": "read"},
    {"name": "approval_request:update", "description": "Update approval requests", "resource": "approval_request", "action": "update"},
    {"name": "approval_request:delete", "description": "Delete approval requests", "resource": "approval_request", "action": "delete"},
    {"name": "approval_request:approve", "description": "Approve requests", "resource": "approval_request", "action": "approve"},
    {"name": "approval_request:reject", "description": "Reject requests", "resource": "approval_request", "action": "reject"},
    {"name": "approval_request:cancel", "description": "Cancel requests", "resource": "approval_request", "action": "cancel"},
    {"name": "approval_request:export", "description": "Export approval requests", "resource": "approval_request", "action": "export"},

    # ==================== ORGANIZATION ====================
    # Department
    {"name": "department:create", "description": "Create departments", "resource": "department", "action": "create"},
    {"name": "department:read", "description": "View departments", "resource": "department", "action": "read"},
    {"name": "department:update", "description": "Update departments", "resource": "department", "action": "update"},
    {"name": "department:delete", "description": "Delete departments", "resource": "department", "action": "delete"},
    {"name": "department:export", "description": "Export departments", "resource": "department", "action": "export"},

    # Location
    {"name": "location:create", "description": "Create locations", "resource": "location", "action": "create"},
    {"name": "location:read", "description": "View locations", "resource": "location", "action": "read"},
    {"name": "location:update", "description": "Update locations", "resource": "location", "action": "update"},
    {"name": "location:delete", "description": "Delete locations", "resource": "location", "action": "delete"},
    {"name": "location:export", "description": "Export locations", "resource": "location", "action": "export"},

    # ==================== HR MANAGEMENT ====================
    # Employee
    {"name": "employee:create", "description": "Create employees", "resource": "employee", "action": "create"},
    {"name": "employee:read", "description": "View employees", "resource": "employee", "action": "read"},
    {"name": "employee:update", "description": "Update employees", "resource": "employee", "action": "update"},
    {"name": "employee:delete", "description": "Delete employees", "resource": "employee", "action": "delete"},
    {"name": "employee:export", "description": "Export employee data", "resource": "employee", "action": "export"},

    # Shift Type
    {"name": "shift_type:create", "description": "Create shift types", "resource": "shift_type", "action": "create"},
    {"name": "shift_type:read", "description": "View shift types", "resource": "shift_type", "action": "read"},
    {"name": "shift_type:update", "description": "Update shift types", "resource": "shift_type", "action": "update"},
    {"name": "shift_type:delete", "description": "Delete shift types", "resource": "shift_type", "action": "delete"},
    {"name": "shift_type:export", "description": "Export shift types", "resource": "shift_type", "action": "export"},

    # Shifts
    {"name": "shift:create", "description": "Create shifts", "resource": "shift", "action": "create"},
    {"name": "shift:read", "description": "View shifts", "resource": "shift", "action": "read"},
    {"name": "shift:update", "description": "Update shifts", "resource": "shift", "action": "update"},
    {"name": "shift:delete", "description": "Delete shifts", "resource": "shift", "action": "delete"},
    {"name": "shift:assign", "description": "Assign shifts to employees", "resource": "shift", "action": "assign"},
    {"name": "shift:export", "description": "Export shifts", "resource": "shift", "action": "export"},

    # Attendance
    {"name": "attendance:create", "description": "Create attendance records", "resource": "attendance", "action": "create"},
    {"name": "attendance:read", "description": "View attendance", "resource": "attendance", "action": "read"},
    {"name": "attendance:update", "description": "Update attendance", "resource": "attendance", "action": "update"},
    {"name": "attendance:delete", "description": "Delete attendance records", "resource": "attendance", "action": "delete"},
    {"name": "attendance:approve", "description": "Approve attendance", "resource": "attendance", "action": "approve"},
    {"name": "attendance:export", "description": "Export attendance data", "resource": "attendance", "action": "export"},

    # Salary
    {"name": "salary:create", "description": "Create salary records", "resource": "salary", "action": "create"},
    {"name": "salary:read", "description": "View salaries", "resource": "salary", "action": "read"},
    {"name": "salary:update", "description": "Update salaries", "resource": "salary", "action": "update"},
    {"name": "salary:delete", "description": "Delete salary records", "resource": "salary", "action": "delete"},
    {"name": "salary:approve", "description": "Approve salary payments", "resource": "salary", "action": "approve"},
    {"name": "salary:process", "description": "Process salary payments", "resource": "salary", "action": "process"},
    {"name": "salary:export", "description": "Export salary data", "resource": "salary", "action": "export"},

    # Days Off
    {"name": "days_off:create", "description": "Create days off requests", "resource": "days_off", "action": "create"},
    {"name": "days_off:read", "description": "View days off", "resource": "days_off", "action": "read"},
    {"name": "days_off:update", "description": "Update days off", "resource": "days_off", "action": "update"},
    {"name": "days_off:delete", "description": "Delete days off", "resource": "days_off", "action": "delete"},
    {"name": "days_off:approve", "description": "Approve days off requests", "resource": "days_off", "action": "approve"},
    {"name": "days_off:reject", "description": "Reject days off requests", "resource": "days_off", "action": "reject"},
    {"name": "days_off:export", "description": "Export days off data", "resource": "days_off", "action": "export"},

    # Deduction Types
    {"name": "deduction_type:create", "description": "Create deduction types", "resource": "deduction_type", "action": "create"},
    {"name": "deduction_type:read", "description": "View deduction types", "resource": "deduction_type", "action": "read"},
    {"name": "deduction_type:update", "description": "Update deduction types", "resource": "deduction_type", "action": "update"},
    {"name": "deduction_type:delete", "description": "Delete deduction types", "resource": "deduction_type", "action": "delete"},
    {"name": "deduction_type:export", "description": "Export deduction types", "resource": "deduction_type", "action": "export"},

    # Employee Deductions
    {"name": "employee_deduction:create", "description": "Create employee deductions", "resource": "employee_deduction", "action": "create"},
    {"name": "employee_deduction:read", "description": "View employee deductions", "resource": "employee_deduction", "action": "read"},
    {"name": "employee_deduction:update", "description": "Update employee deductions", "resource": "employee_deduction", "action": "update"},
    {"name": "employee_deduction:delete", "description": "Delete employee deductions", "resource": "employee_deduction", "action": "delete"},
    {"name": "employee_deduction:approve", "description": "Approve deductions", "resource": "employee_deduction", "action": "approve"},
    {"name": "employee_deduction:export", "description": "Export employee deductions", "resource": "employee_deduction", "action": "export"},

    # Tickets
    {"name": "ticket:create", "description": "Create tickets", "resource": "ticket", "action": "create"},
    {"name": "ticket:read", "description": "View tickets", "resource": "ticket", "action": "read"},
    {"name": "ticket:update", "description": "Update tickets", "resource": "ticket", "action": "update"},
    {"name": "ticket:delete", "description": "Delete tickets", "resource": "ticket", "action": "delete"},
    {"name": "ticket:export", "description": "Export tickets", "resource": "ticket", "action": "export"},

    # ==================== INVENTORY ====================
    # Item
    {"name": "item:create", "description": "Create inventory items", "resource": "item", "action": "create"},
    {"name": "item:read", "description": "View inventory items", "resource": "item", "action": "read"},
    {"name": "item:update", "description": "Update inventory items", "resource": "item", "action": "update"},
    {"name": "item:delete", "description": "Delete inventory items", "resource": "item", "action": "delete"},
    {"name": "item:export", "description": "Export items", "resource": "item", "action": "export"},

    # Product
    {"name": "product:create", "description": "Create products", "resource": "product", "action": "create"},
    {"name": "product:read", "description": "View products", "resource": "product", "action": "read"},
    {"name": "product:update", "description": "Update products", "resource": "product", "action": "update"},
    {"name": "product:delete", "description": "Delete products", "resource": "product", "action": "delete"},
    {"name": "product:export", "description": "Export products", "resource": "product", "action": "export"},

    # Stock Level
    {"name": "stock_level:create", "description": "Create stock levels", "resource": "stock_level", "action": "create"},
    {"name": "stock_level:read", "description": "View stock levels", "resource": "stock_level", "action": "read"},
    {"name": "stock_level:update", "description": "Update stock levels", "resource": "stock_level", "action": "update"},
    {"name": "stock_level:delete", "description": "Delete stock levels", "resource": "stock_level", "action": "delete"},
    {"name": "stock_level:adjust", "description": "Adjust stock levels", "resource": "stock_level", "action": "adjust"},
    {"name": "stock_level:export", "description": "Export stock levels", "resource": "stock_level", "action": "export"},

    # Category
    {"name": "category:create", "description": "Create categories", "resource": "category", "action": "create"},
    {"name": "category:read", "description": "View categories", "resource": "category", "action": "read"},
    {"name": "category:update", "description": "Update categories", "resource": "category", "action": "update"},
    {"name": "category:delete", "description": "Delete categories", "resource": "category", "action": "delete"},
    {"name": "category:export", "description": "Export categories", "resource": "category", "action": "export"},

    # Refill Kitchen Item
    {"name": "refill_kitchen_item:create", "description": "Create refill requests", "resource": "refill_kitchen_item", "action": "create"},
    {"name": "refill_kitchen_item:read", "description": "View refill requests", "resource": "refill_kitchen_item", "action": "read"},

    # Order
    {"name": "order:read", "description": "View orders", "resource": "order", "action": "read"},
    {"name": "order:export", "description": "Export orders", "resource": "order", "action": "export"},

    # ==================== STOCK OPERATION ====================
    # Reorder Request
    {"name": "reorder_request:create", "description": "Create reorder requests", "resource": "reorder_request", "action": "create"},
    {"name": "reorder_request:read", "description": "View reorder requests", "resource": "reorder_request", "action": "read"},
    {"name": "reorder_request:update", "description": "Update reorder requests", "resource": "reorder_request", "action": "update"},
    {"name": "reorder_request:delete", "description": "Delete reorder requests", "resource": "reorder_request", "action": "delete"},
    {"name": "reorder_request:approve", "description": "Approve reorder requests", "resource": "reorder_request", "action": "approve"},
    {"name": "reorder_request:reject", "description": "Reject reorder requests", "resource": "reorder_request", "action": "reject"},
    {"name": "reorder_request:export", "description": "Export reorder requests", "resource": "reorder_request", "action": "export"},

    # Stock Transfer
    {"name": "stock_transfer:create", "description": "Create stock transfers", "resource": "stock_transfer", "action": "create"},
    {"name": "stock_transfer:read", "description": "View stock transfers", "resource": "stock_transfer", "action": "read"},
    {"name": "stock_transfer:update", "description": "Update stock transfers", "resource": "stock_transfer", "action": "update"},
    {"name": "stock_transfer:delete", "description": "Delete stock transfers", "resource": "stock_transfer", "action": "delete"},
    {"name": "stock_transfer:approve", "description": "Approve stock transfers", "resource": "stock_transfer", "action": "approve"},
    {"name": "stock_transfer:cancel", "description": "Cancel stock transfers", "resource": "stock_transfer", "action": "cancel"},
    {"name": "stock_transfer:export", "description": "Export stock transfers", "resource": "stock_transfer", "action": "export"},

    # Stock Movement
    {"name": "stock_movement:create", "description": "Create stock movements", "resource": "stock_movement", "action": "create"},
    {"name": "stock_movement:read", "description": "View stock movements", "resource": "stock_movement", "action": "read"},
    {"name": "stock_movement:update", "description": "Update stock movements", "resource": "stock_movement", "action": "update"},
    {"name": "stock_movement:delete", "description": "Delete stock movements", "resource": "stock_movement", "action": "delete"},
    {"name": "stock_movement:export", "description": "Export stock movements", "resource": "stock_movement", "action": "export"},

    # Inventory Count
    {"name": "inventory_count:create", "description": "Create inventory counts", "resource": "inventory_count", "action": "create"},
    {"name": "inventory_count:read", "description": "View inventory counts", "resource": "inventory_count", "action": "read"},
    {"name": "inventory_count:update", "description": "Update inventory counts", "resource": "inventory_count", "action": "update"},
    {"name": "inventory_count:delete", "description": "Delete inventory counts", "resource": "inventory_count", "action": "delete"},
    {"name": "inventory_count:approve", "description": "Approve inventory counts", "resource": "inventory_count", "action": "approve"},
    {"name": "inventory_count:export", "description": "Export inventory counts", "resource": "inventory_count", "action": "export"},

    # Inventory Mismatch Reason
    {"name": "mismatch_reason:create", "description": "Create mismatch reasons", "resource": "mismatch_reason", "action": "create"},
    {"name": "mismatch_reason:read", "description": "View mismatch reasons", "resource": "mismatch_reason", "action": "read"},
    {"name": "mismatch_reason:update", "description": "Update mismatch reasons", "resource": "mismatch_reason", "action": "update"},
    {"name": "mismatch_reason:delete", "description": "Delete mismatch reasons", "resource": "mismatch_reason", "action": "delete"},
    {"name": "mismatch_reason:export", "description": "Export mismatch reasons", "resource": "mismatch_reason", "action": "export"},

    # Stock Type
    {"name": "stock_type:create", "description": "Create stock types", "resource": "stock_type", "action": "create"},
    {"name": "stock_type:read", "description": "View stock types", "resource": "stock_type", "action": "read"},
    {"name": "stock_type:update", "description": "Update stock types", "resource": "stock_type", "action": "update"},
    {"name": "stock_type:delete", "description": "Delete stock types", "resource": "stock_type", "action": "delete"},
    {"name": "stock_type:export", "description": "Export stock types", "resource": "stock_type", "action": "export"},

    # ==================== PURCHASE ====================
    # Purchase Order
    {"name": "purchase_order:create", "description": "Create purchase orders", "resource": "purchase_order", "action": "create"},
    {"name": "purchase_order:read", "description": "View purchase orders", "resource": "purchase_order", "action": "read"},
    {"name": "purchase_order:update", "description": "Update purchase orders", "resource": "purchase_order", "action": "update"},
    {"name": "purchase_order:delete", "description": "Delete purchase orders", "resource": "purchase_order", "action": "delete"},
    {"name": "purchase_order:approve", "description": "Approve purchase orders", "resource": "purchase_order", "action": "approve"},
    {"name": "purchase_order:reject", "description": "Reject purchase orders", "resource": "purchase_order", "action": "reject"},
    {"name": "purchase_order:cancel", "description": "Cancel purchase orders", "resource": "purchase_order", "action": "cancel"},
    {"name": "purchase_order:export", "description": "Export purchase orders", "resource": "purchase_order", "action": "export"},

    # Supplier
    {"name": "supplier:create", "description": "Create suppliers", "resource": "supplier", "action": "create"},
    {"name": "supplier:read", "description": "View suppliers", "resource": "supplier", "action": "read"},
    {"name": "supplier:update", "description": "Update suppliers", "resource": "supplier", "action": "update"},
    {"name": "supplier:delete", "description": "Delete suppliers", "resource": "supplier", "action": "delete"},
    {"name": "supplier:export", "description": "Export suppliers", "resource": "supplier", "action": "export"},

    # Good Receipt
    {"name": "good_receipt:create", "description": "Create good receipts", "resource": "good_receipt", "action": "create"},
    {"name": "good_receipt:read", "description": "View good receipts", "resource": "good_receipt", "action": "read"},
    {"name": "good_receipt:update", "description": "Update good receipts", "resource": "good_receipt", "action": "update"},
    {"name": "good_receipt:delete", "description": "Delete good receipts", "resource": "good_receipt", "action": "delete"},
    {"name": "good_receipt:approve", "description": "Approve good receipts", "resource": "good_receipt", "action": "approve"},
    {"name": "good_receipt:export", "description": "Export good receipts", "resource": "good_receipt", "action": "export"},

    # PO Payment
    {"name": "po_payment:create", "description": "Create PO payments", "resource": "po_payment", "action": "create"},
    {"name": "po_payment:read", "description": "View PO payments", "resource": "po_payment", "action": "read"},
    {"name": "po_payment:update", "description": "Update PO payments", "resource": "po_payment", "action": "update"},
    {"name": "po_payment:delete", "description": "Delete PO payments", "resource": "po_payment", "action": "delete"},
    {"name": "po_payment:approve", "description": "Approve PO payments", "resource": "po_payment", "action": "approve"},
    {"name": "po_payment:export", "description": "Export PO payments", "resource": "po_payment", "action": "export"},

    # ==================== LOGISTIC ====================
    # Shipment
    {"name": "shipment:create", "description": "Create shipments", "resource": "shipment", "action": "create"},
    {"name": "shipment:read", "description": "View shipments", "resource": "shipment", "action": "read"},
    {"name": "shipment:update", "description": "Update shipments", "resource": "shipment", "action": "update"},
    {"name": "shipment:delete", "description": "Delete shipments", "resource": "shipment", "action": "delete"},
    {"name": "shipment:assign", "description": "Assign shipments to drivers", "resource": "shipment", "action": "assign"},
    {"name": "shipment:dispatch", "description": "Dispatch shipments", "resource": "shipment", "action": "dispatch"},
    {"name": "shipment:complete", "description": "Complete shipments", "resource": "shipment", "action": "complete"},
    {"name": "shipment:export", "description": "Export shipments", "resource": "shipment", "action": "export"},

    # Driver
    {"name": "driver:create", "description": "Create drivers", "resource": "driver", "action": "create"},
    {"name": "driver:read", "description": "View drivers", "resource": "driver", "action": "read"},
    {"name": "driver:update", "description": "Update drivers", "resource": "driver", "action": "update"},
    {"name": "driver:delete", "description": "Delete drivers", "resource": "driver", "action": "delete"},
    {"name": "driver:activate", "description": "Activate/Deactivate drivers", "resource": "driver", "action": "activate"},
    {"name": "driver:export", "description": "Export drivers", "resource": "driver", "action": "export"},

    # License Expiry
    {"name": "license_expiry:export", "description": "Export license expiry", "resource": "license_expiry", "action": "export"},

    # Vehicle
    {"name": "vehicle:create", "description": "Create vehicles", "resource": "vehicle", "action": "create"},
    {"name": "vehicle:read", "description": "View vehicles", "resource": "vehicle", "action": "read"},
    {"name": "vehicle:update", "description": "Update vehicles", "resource": "vehicle", "action": "update"},
    {"name": "vehicle:delete", "description": "Delete vehicles", "resource": "vehicle", "action": "delete"},
    {"name": "vehicle:activate", "description": "Activate/Deactivate vehicles", "resource": "vehicle", "action": "activate"},
    {"name": "vehicle:export", "description": "Export vehicles", "resource": "vehicle", "action": "export"},

    # Vehicle Available
    {"name": "vehicle_available:export", "description": "Export vehicle availability", "resource": "vehicle_available", "action": "export"},

    # Maintenance Due
    {"name": "maintenance_due:export", "description": "Export maintenance due", "resource": "maintenance_due", "action": "export"},

    # Document Expiry
    {"name": "document_expiry:export", "description": "Export document expiry", "resource": "document_expiry", "action": "export"},

    # ==================== REPORTS ====================
    {"name": "reports:read", "description": "View reports", "resource": "reports", "action": "read"},
    {"name": "reports:export", "description": "Export reports", "resource": "reports", "action": "export"},

    # ==================== SYSTEM ====================
    {"name": "system:admin", "description": "System administration", "resource": "system", "action": "admin"},
    {"name": "system:backup", "description": "Backup & restore", "resource": "system", "action": "backup"},
    {"name": "system:configure", "description": "System configuration", "resource": "system", "action": "configure"},
    {"name": "system:audit", "description": "View audit logs", "resource": "system", "action": "audit"},
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