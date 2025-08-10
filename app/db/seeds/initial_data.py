# import logging
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# from app.models.auth.user import User
# from app.models.auth.role import Role
# from app.models.auth.permission import Permission
# from app.models.hr.department import Department
# from app.models.inventory.unit import Unit
# from app.models.inventory.category import Category
# from app.core.security import get_password_hash

# logger = logging.getLogger(__name__)

# async def create_initial_data(session: AsyncSession):
#     """Create initial data for the application"""
#     try:
#         logger.info("📋 Creating initial data...")
        
#         # Create initial roles
#         await create_initial_roles(session)
        
#         # Create initial permissions
#         await create_initial_permissions(session)
        
#         # Create admin user
#         await create_admin_user(session)
        
#         # Create initial departments
#         await create_initial_departments(session)
        
#         # Create initial inventory units
#         await create_initial_units(session)
        
#         # Create initial categories
#         await create_initial_categories(session)
        
#         await session.commit()
#         logger.info("✅ Initial data created successfully")
        
#     except Exception as e:
#         logger.error(f"❌ Error creating initial data: {str(e)}")
#         await session.rollback()
#         raise

# async def create_initial_roles(session: AsyncSession):
#     """Create initial system roles"""
#     roles_data = [
#         {"name": "super_admin", "description": "Super Administrator with full access"},
#         {"name": "admin", "description": "Administrator with management access"},
#         {"name": "manager", "description": "Manager with departmental access"},
#         {"name": "employee", "description": "Regular employee with basic access"},
#         {"name": "viewer", "description": "Read-only access"},
#     ]
    
#     for role_data in roles_data:
#         # Check if role exists
#         result = await session.execute(
#             select(Role).where(Role.name == role_data["name"])
#         )
#         existing_role = result.scalar_one_or_none()
        
#         if not existing_role:
#             role = Role(**role_data)
#             session.add(role)
#             logger.info(f"Created role: {role_data['name']}")

# async def create_initial_permissions(session: AsyncSession):
#     """Create initial system permissions"""
#     permissions_data = [
#         {"name": "read_inventory", "description": "Read inventory data"},
#         {"name": "write_inventory", "description": "Write inventory data"},
#         {"name": "read_hr", "description": "Read HR data"},
#         {"name": "write_hr", "description": "Write HR data"},
#         {"name": "read_purchase", "description": "Read purchase data"},
#         {"name": "write_purchase", "description": "Write purchase data"},
#         {"name": "read_logistics", "description": "Read logistics data"},
#         {"name": "write_logistics", "description": "Write logistics data"},
#         {"name": "read_reports", "description": "Read reports"},
#         {"name": "admin_access", "description": "Administrative access"},
#     ]
    
#     for perm_data in permissions_data:
#         # Check if permission exists
#         result = await session.execute(
#             select(Permission).where(Permission.name == perm_data["name"])
#         )
#         existing_perm = result.scalar_one_or_none()
        
#         if not existing_perm:
#             permission = Permission(**perm_data)
#             session.add(permission)
#             logger.info(f"Created permission: {perm_data['name']}")

# async def create_admin_user(session: AsyncSession):
#     """Create initial admin user"""
#     # Check if admin user exists
#     result = await session.execute(
#         select(User).where(User.email == "admin@ai-retail.com")
#     )
#     existing_user = result.scalar_one_or_none()
    
#     if not existing_user:
#         admin_user = User(
#             email="admin@ai-retail.com",
#             username="admin",
#             full_name="System Administrator",
#             hashed_password=get_password_hash("admin123"),
#             is_active=True,
#             is_superuser=True
#         )
#         session.add(admin_user)
#         logger.info("Created admin user: admin@ai-retail.com")

# async def create_initial_departments(session: AsyncSession):
#     """Create initial departments"""
#     departments_data = [
#         {"name": "Administration", "description": "Administrative department"},
#         {"name": "Sales", "description": "Sales department"},
#         {"name": "Inventory", "description": "Inventory management"},
#         {"name": "HR", "description": "Human Resources"},
#         {"name": "IT", "description": "Information Technology"},
#     ]
    
#     for dept_data in departments_data:
#         # Check if department exists
#         result = await session.execute(
#             select(Department).where(Department.name == dept_data["name"])
#         )
#         existing_dept = result.scalar_one_or_none()
        
#         if not existing_dept:
#             department = Department(**dept_data)
#             session.add(department)
#             logger.info(f"Created department: {dept_data['name']}")

# async def create_initial_units(session: AsyncSession):
#     """Create initial inventory units"""
#     units_data = [
#         {"name": "PCS", "description": "Pieces"},
#         {"name": "KG", "description": "Kilograms"},
#         {"name": "L", "description": "Liters"},
#         {"name": "M2", "description": "Square Meters"},
#         {"name": "M3", "description": "Cubic Meters"},
#         {"name": "LM", "description": "Linear Meters"},
#     ]
    
#     for unit_data in units_data:
#         # Check if unit exists
#         result = await session.execute(
#             select(Unit).where(Unit.name == unit_data["name"])
#         )
#         existing_unit = result.scalar_one_or_none()
        
#         if not existing_unit:
#             unit = Unit(**unit_data)
#             session.add(unit)
#             logger.info(f"Created unit: {unit_data['name']}")

# async def create_initial_categories(session: AsyncSession):
#     """Create initial inventory categories"""
#     categories_data = [
#         {"name": "Raw Materials", "description": "Raw materials for production"},
#         {"name": "Finished Goods", "description": "Finished products ready for sale"},
#         {"name": "Consumables", "description": "Consumable items"},
#         {"name": "Equipment", "description": "Equipment and machinery"},
#         {"name": "Office Supplies", "description": "Office supplies and stationery"},
#     ]
    
#     for cat_data in categories_data:
#         # Check if category exists
#         result = await session.execute(
#             select(Category).where(Category.name == cat_data["name"])
#         )
#         existing_cat = result.scalar_one_or_none()
        
#         if not existing_cat:
#             category = Category(**cat_data)
#             session.add(category)
#             logger.info(f"Created category: {cat_data['name']}")