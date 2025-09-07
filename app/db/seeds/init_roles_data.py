import os
import sys
import asyncio

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, project_root)

from sqlalchemy import select


roles_data = [
    # =================== EXECUTIVE & ADMINISTRATIVE ROLES ===================
    {
        "name": "super_admin", 
        "description": "Super Administrator with full system access and control",
        "is_system_role": True
    },
    {
        "name": "cafe_owner", 
        "description": "Cafe Owner with complete business oversight and decision-making authority"
    },
    {
        "name": "general_manager", 
        "description": "General Manager overseeing all cafe operations and departments"
    },
    {
        "name": "admin", 
        "description": "System Administrator with management access to core functions"
    },
    
    # =================== DEPARTMENT MANAGEMENT ROLES ===================
    {
        "name": "branch_manager", 
        "description": "Branch Manager overseeing specific cafe location operations"
    },
    {
        "name": "shift_supervisor", 
        "description": "Shift Supervisor managing staff and operations during specific shifts"
    },
    
    # =================== INVENTORY & PROCUREMENT ROLES ===================
    {
        "name": "inventory_manager", 
        "description": "Inventory Manager controlling stock levels, procurement, and supply chain"
    },
    {
        "name": "warehouse_manager", 
        "description": "Warehouse Manager overseeing storage, receiving, and distribution operations"
    },
    {
        "name": "purchase_manager", 
        "description": "Purchase Manager handling supplier relationships and purchase orders"
    },
    
    # =================== FINANCIAL & HR ROLES ===================
    {
        "name": "finance_manager", 
        "description": "Finance Manager overseeing financial operations, budgets, and cost control"
    },
    {
        "name": "hr_manager", 
        "description": "HR Manager handling employee relations, recruitment, and policy management"
    },
    
    # =================== LOGISTICS & DELIVERY ROLES ===================
    {
        "name": "logistics_manager", 
        "description": "Logistics Manager coordinating deliveries, transportation, and supply chain"
    },
    {
        "name": "delivery_driver", 
        "description": "Delivery Driver responsible for transportation and delivery operations"
    },
    {
        "name": "logistics_operator", 
        "description": "Logistics Operator supporting shipping, receiving, and tracking operations"
    },
    
    # =================== CAFE OPERATIONS ROLES ===================
    {
        "name": "cafe_manager", 
        "description": "Cafe Manager overseeing front-of-house operations and customer service"
    },
    {
        "name": "kitchen_manager", 
        "description": "Kitchen Manager supervising food preparation and kitchen operations"
    },
    {
        "name": "kitchen_staff", 
        "description": "Kitchen Staff handling food preparation and kitchen support"
    },
    {
        "name": "cashier", 
        "description": "Cashier managing point-of-sale transactions and customer payments"
    },
    
    # =================== MAINTENANCE & TECHNICAL ROLES ===================
    {
        "name": "it_administrator", 
        "description": "IT Administrator managing system infrastructure and technical support"
    },
    # =================== CUSTOMER & VENDOR RELATIONS ===================
    {
        "name": "customer_service_manager", 
        "description": "Customer Service Manager handling customer relations and feedback"
    },
    
    # =================== BASIC ACCESS ROLES ===================
    {
        "name": "manager", 
        "description": "Generic Manager role with departmental access and oversight"
    },
    {
        "name": "supervisor", 
        "description": "Supervisor with team leadership and operational oversight"
    },
    {
        "name": "employee", 
        "description": "Regular Employee with basic operational access and task management"
    },
    {
        "name": "viewer", 
        "description": "Read-only access for monitoring and reporting purposes"
    },
    {
        "name": "guest", 
        "description": "Limited guest access for external stakeholders"
    }
]

# =================== SEEDING SCRIPT ===================
async def seed_roles(session):
    """Seed roles into the database"""
    from app.models.auth.role import Role
    
    created_roles = []
    for role_data in roles_data:
        # Check if role already exists
        existing_role = await session.execute(
            select(Role).where(Role.name == role_data["name"])
        )
        if existing_role.scalar_one_or_none():
            continue
            
        # Create new role
        role = Role(
            name=role_data["name"],
            description=role_data["description"],
            is_system_role=role_data.get("is_system_role", False),
            is_active=True
        )
        session.add(role)
        created_roles.append(role_data["name"])
    
    await session.commit()
    return created_roles


# =================== USAGE EXAMPLE ===================

# To seed roles in your database:
from app.core.database import get_async_session

async def main():
    """Main function to run the roles seeding process"""
    try:
        # Use async for instead of async with for generator-based sessions
        async for session in get_async_session():
            created_roles = await seed_roles(session)
            print(f"Created {len(created_roles)} roles: {created_roles}")
            print("Cafe Shop Backend Role Definitions Ready!")
            print(f"Total Roles: {len(roles_data)}")
            break  # Only process one session
    except Exception as e:
        print(f"❌ Failed to seed roles: {str(e)}")

# This makes the script runnable
if __name__ == "__main__":
    asyncio.run(main())