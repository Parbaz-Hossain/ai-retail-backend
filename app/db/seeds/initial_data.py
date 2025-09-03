import os
import sys
import asyncio

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, project_root)

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.auth.user import User
from app.models.organization.department import Department
from app.models.inventory.category import Category
from app.core.security import get_password_hash
from app.core.database import get_async_session

logger = logging.getLogger(__name__)

async def create_initial_data(session: AsyncSession):
    """Create initial data for the application"""
    try:
        logger.info("📋 Creating initial data...")
                
        # Create admin user
        await create_super_admin_user(session)
        
        # Create initial departments
        await create_initial_departments(session)
        
        # Create initial categories
        await create_initial_categories(session)
        
        await session.commit()
        logger.info("✅ Initial data created successfully")
        return True  # Return True on success
        
    except Exception as e:
        logger.error(f"❌ Error creating initial data: {str(e)}")
        await session.rollback()
        raise

async def create_super_admin_user(session: AsyncSession):
    """Create initial super admin user"""
    # Check if admin user exists
    result = await session.execute(
        select(User).where(User.email == "super_admin@airetail.com")
    )
    existing_user = result.scalar_one_or_none()
    
    if not existing_user:
        admin_user = User(
            email="super_admin@airetail.com",
            username="super_admin",
            full_name="System Administrator",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_superuser=True
        )
        session.add(admin_user)
        logger.info("Created super admin user: super_admin@airetail.com")

async def create_initial_departments(session: AsyncSession):
    """Create initial departments"""
    departments_data = [
        {"name": "Administration", "description": "Administrative department"},
        {"name": "Sales", "description": "Sales department"},
        {"name": "Inventory", "description": "Inventory management"},
        {"name": "Purchase", "description": "Purchase management"},
        {"name": "Logistics", "description": "Logistics management"},
        {"name": "HR", "description": "Human Resources"},
        {"name": "IT", "description": "Information Technology"},
    ]
    
    for dept_data in departments_data:
        # Check if department exists
        result = await session.execute(
            select(Department).where(Department.name == dept_data["name"])
        )
        existing_dept = result.scalar_one_or_none()
        
        if not existing_dept:
            department = Department(**dept_data)
            session.add(department)
            logger.info(f"Created department: {dept_data['name']}")

async def create_initial_categories(session: AsyncSession):
    """Create initial inventory categories"""
    categories_data = [
        {"name": "Raw Materials", "description": "Raw materials for production"},
        {"name": "Finished Goods", "description": "Finished products ready for sale"},
        {"name": "Consumables", "description": "Consumable items"},
        {"name": "Equipment", "description": "Equipment and machinery"},
        {"name": "Office Supplies", "description": "Office supplies and stationery"},
    ]
    
    for cat_data in categories_data:
        # Check if category exists
        result = await session.execute(
            select(Category).where(Category.name == cat_data["name"])
        )
        existing_cat = result.scalar_one_or_none()
        
        if not existing_cat:
            category = Category(**cat_data)
            session.add(category)
            logger.info(f"Created category: {cat_data['name']}")

if __name__ == "__main__":
    async def main():
        """Main function to run the seeding process"""
        try:
            # Handle both context manager and generator-based sessions
            session_gen = get_async_session()
            if hasattr(session_gen, '__aenter__'):
                # It's a context manager
                async with session_gen as session:
                    success = await create_initial_data(session)
                    if success:
                        print("✅ Initial data setup complete.")
            else:
                # It's a generator
                async for session in session_gen:
                    success = await create_initial_data(session)
                    if success:
                        print("✅ Initial data setup complete.")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Failed to setup initial data: {str(e)}")
            print(f"❌ Failed to setup initial data: {str(e)}")

    # This makes the script runnable
    asyncio.run(main())