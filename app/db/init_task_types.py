"""
Initialize default task types in the database
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.task.task_type import TaskType

async def init_default_task_types(db: AsyncSession):
    """Initialize default task types"""
    default_task_types = [
        # Inventory Tasks
        {
            "name": "Low Stock Alert",
            "category": "INVENTORY",
            "description": "Alert when item stock falls below reorder point",
            "auto_assign_enabled": True,
            "auto_assign_rules": {"roles": ["INVENTORY_MANAGER", "BRANCH_MANAGER"]},
            "default_priority": "HIGH",
            "sla_hours": 24
        },
        {
            "name": "Reorder Request Approval",
            "category": "INVENTORY",
            "description": "Review and approve reorder requests",
            "requires_approval": True,
            "approval_roles": ["BRANCH_MANAGER", "WAREHOUSE_MANAGER"],
            "default_priority": "MEDIUM",
            "sla_hours": 48
        },
        {
            "name": "Stock Count",
            "category": "INVENTORY",
            "description": "Perform physical inventory count",
            "default_priority": "MEDIUM",
            "default_estimated_hours": 4.0,
            "sla_hours": 72
        },
        # HR Tasks
        {
            "name": "Salary Generation",
            "category": "HR",
            "description": "Generate monthly salary for employees",
            "auto_assign_enabled": True,
            "auto_assign_rules": {"roles": ["HR_MANAGER"]},
            "default_priority": "HIGH",
            "sla_hours": 48
        },
        {
            "name": "Attendance Review",
            "category": "HR",
            "description": "Review and approve employee attendance",
            "default_priority": "MEDIUM",
            "sla_hours": 24
        },
        {
            "name": "Employee Onboarding",
            "category": "HR",
            "description": "Complete new employee onboarding process",
            "default_priority": "HIGH",
            "default_estimated_hours": 8.0,
            "sla_hours": 48
        },
        # Purchase Tasks
        {
            "name": "Purchase Order Approval",
            "category": "PURCHASE",
            "description": "Review and approve purchase orders",
            "requires_approval": True,
            "approval_roles": ["BRANCH_MANAGER", "PURCHASE_MANAGER"],
            "default_priority": "MEDIUM",
            "sla_hours": 48
        },
        {
            "name": "Supplier Evaluation",
            "category": "PURCHASE",
            "description": "Evaluate and review supplier performance",
            "default_priority": "LOW",
            "default_estimated_hours": 2.0,
            "sla_hours": 168  # 1 week
        },
        {
            "name": "Goods Receipt Verification",
            "category": "PURCHASE",
            "description": "Verify received goods against purchase order",
            "default_priority": "HIGH",
            "sla_hours": 24
        },
        # Logistics Tasks
        {
            "name": "Shipment Delivery",
            "category": "LOGISTICS",
            "description": "Complete shipment delivery",
            "auto_assign_enabled": True,
            "auto_assign_rules": {"reference_field": "driver_id"},
            "default_priority": "HIGH",
            "sla_hours": 24
        },
        {
            "name": "Shipment Monitoring",
            "category": "LOGISTICS",
            "description": "Monitor shipment progress",
            "auto_assign_enabled": True,
            "auto_assign_rules": {"roles": ["LOGISTICS_MANAGER"]},
            "default_priority": "MEDIUM",
            "sla_hours": 48
        },
        {
            "name": "Vehicle Maintenance",
            "category": "LOGISTICS",
            "description": "Perform vehicle maintenance",
            "default_priority": "MEDIUM",
            "default_estimated_hours": 4.0,
            "sla_hours": 168
        },
        # Maintenance Tasks
        {
            "name": "Equipment Maintenance",
            "category": "MAINTENANCE",
            "description": "Perform scheduled equipment maintenance",
            "auto_assign_enabled": True,
            "auto_assign_rules": {"roles": ["MAINTENANCE_STAFF", "BRANCH_MANAGER"]},
            "default_priority": "MEDIUM",
            "default_estimated_hours": 2.0,
            "sla_hours": 72
        },
        {
            "name": "Safety Inspection",
            "category": "MAINTENANCE",
            "description": "Perform safety equipment inspection",
            "default_priority": "HIGH",
            "default_estimated_hours": 1.0,
            "sla_hours": 48
        },
        # Operations Tasks
        {
            "name": "Monthly Report Generation",
            "category": "OPERATIONS",
            "description": "Generate monthly operational reports",
            "is_recurring": True,
            "recurrence_pattern": "MONTHLY",
            "default_priority": "MEDIUM",
            "default_estimated_hours": 4.0,
            "sla_hours": 72
        },
        {
            "name": "Menu Planning",
            "category": "OPERATIONS",
            "description": "Plan seasonal menu and specialties",
            "auto_assign_enabled": True,
            "auto_assign_rules": {"roles": ["CHEF", "BRANCH_MANAGER"]},
            "default_priority": "MEDIUM",
            "default_estimated_hours": 6.0,
            "sla_hours": 168
        }
    ]
    
    for task_type_data in default_task_types:
        # Check if task type already exists
        result = await db.execute(
            select(TaskType).where(
                and_(
                    TaskType.name == task_type_data["name"],
                    TaskType.category == task_type_data["category"]
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            task_type = TaskType(**task_type_data)
            db.add(task_type)
    
    await db.commit()