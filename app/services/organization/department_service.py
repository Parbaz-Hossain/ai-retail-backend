from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_
from app.models.organization.department import Department
from app.schemas.organization.department_schema import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import logger

class DepartmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_department(self, department_data: DepartmentCreate, current_user_id: int) -> Department:
        """Create a new department"""
        try:
            # Check if department name already exists
            existing = self.db.query(Department).filter(
                Department.name == department_data.name,
                Department.is_active == True
            ).first()
            
            if existing:
                raise ValidationError(f"Department with name '{department_data.name}' already exists")

            department = Department(
                name=department_data.name,
                description=department_data.description,
                is_active=True
            )
            
            self.db.add(department)
            self.db.commit()
            self.db.refresh(department)
            
            logger.info(f"Department created: {department.name} by user {current_user_id}")
            return department
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating department: {str(e)}")
            raise

    async def get_department(self, department_id: int) -> Department:
        """Get department by ID"""
        department = self.db.query(Department).filter(
            Department.id == department_id,
            Department.is_active == True
        ).first()
        
        if not department:
            raise NotFoundError(f"Department with ID {department_id} not found")
        
        return department

    async def get_departments(
        self, 
        skip: int = 0, 
        limit: int = 100,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[Department]:
        """Get all departments with filtering"""
        query = self.db.query(Department)
        
        if is_active is not None:
            query = query.filter(Department.is_active == is_active)
        
        if search:
            query = query.filter(
                or_(
                    Department.name.ilike(f"%{search}%"),
                    Department.description.ilike(f"%{search}%")
                )
            )
        
        return query.offset(skip).limit(limit).all()

    async def update_department(
        self, 
        department_id: int, 
        department_data: DepartmentUpdate,
        current_user_id: int
    ) -> Department:
        """Update department"""
        department = await self.get_department(department_id)
        
        # Check name uniqueness if name is being updated
        if department_data.name and department_data.name != department.name:
            existing = self.db.query(Department).filter(
                Department.name == department_data.name,
                Department.id != department_id,
                Department.is_active == True
            ).first()
            
            if existing:
                raise ValidationError(f"Department with name '{department_data.name}' already exists")

        update_data = department_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(department, field, value)

        self.db.commit()
        self.db.refresh(department)
        
        logger.info(f"Department updated: {department.name} by user {current_user_id}")
        return department

    async def delete_department(self, department_id: int, current_user_id: int) -> bool:
        """Soft delete department"""
        department = await self.get_department(department_id)
        
        # Check if department has active employees
        from models.hr.employee import Employee
        active_employees = self.db.query(Employee).filter(
            Employee.department_id == department_id,
            Employee.is_active == True
        ).count()
        
        if active_employees > 0:
            raise ValidationError(f"Cannot delete department. It has {active_employees} active employees")

        department.is_active = False
        self.db.commit()
        
        logger.info(f"Department deleted: {department.name} by user {current_user_id}")
        return True