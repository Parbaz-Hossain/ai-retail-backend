from typing import List, Optional
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func
from datetime import date, datetime
from app.models.hr.employee import Employee
from app.models.organization.department import Department
from app.models.organization.location import Location
from app.schemas.hr.employee_schema import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import logger
import uuid

class EmployeeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _generate_employee_id(self) -> str:
        """Generate unique employee ID"""
        prefix = "EMP"
        timestamp = datetime.now().strftime("%y%m")
        
        # Get count of employees created this month
        count = self.db.query(Employee).filter(
            Employee.employee_id.like(f"{prefix}{timestamp}%")
        ).count()
        
        return f"{prefix}{timestamp}{count + 1:04d}"

    async def create_employee(self, employee_data: EmployeeCreate, current_user_id: int) -> Employee:
        """Create a new employee"""
        try:
            # Validate department exists
            department = self.db.query(Department).filter(
                Department.id == employee_data.department_id,
                Department.is_active == True
            ).first()
            if not department:
                raise ValidationError(f"Department with ID {employee_data.department_id} not found")

            # Validate location exists
            location = self.db.query(Location).filter(
                Location.id == employee_data.location_id,
                Location.is_active == True
            ).first()
            if not location:
                raise ValidationError(f"Location with ID {employee_data.location_id} not found")

            # Check if email already exists
            existing_email = self.db.query(Employee).filter(
                Employee.email == employee_data.email,
                Employee.is_active == True
            ).first()
            if existing_email:
                raise ValidationError(f"Employee with email '{employee_data.email}' already exists")

            # Generate employee ID
            employee_id = self._generate_employee_id()

            employee = Employee(
                employee_id=employee_id,
                **employee_data.dict()
            )
            
            self.db.add(employee)
            self.db.commit()
            self.db.refresh(employee)
            
            logger.info(f"Employee created: {employee.employee_id} - {employee.first_name} {employee.last_name} by user {current_user_id}")
            return employee
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating employee: {str(e)}")
            raise

    async def get_employee(self, employee_id: int) -> Employee:
        """Get employee by ID with relationships"""
        employee = self.db.query(Employee).options(
            joinedload(Employee.department),
            joinedload(Employee.location)
        ).filter(
            Employee.id == employee_id,
            Employee.is_active == True
        ).first()
        
        if not employee:
            raise NotFoundError(f"Employee with ID {employee_id} not found")
        
        return employee

    async def get_employee_by_employee_id(self, employee_id: str) -> Employee:
        """Get employee by employee ID"""
        employee = self.db.query(Employee).options(
            joinedload(Employee.department),
            joinedload(Employee.location)
        ).filter(
            Employee.employee_id == employee_id,
            Employee.is_active == True
        ).first()
        
        if not employee:
            raise NotFoundError(f"Employee with ID {employee_id} not found")
        
        return employee

    async def get_employees(
        self,
        skip: int = 0,
        limit: int = 100,
        department_id: Optional[int] = None,
        location_id: Optional[int] = None,
        is_manager: Optional[bool] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> List[Employee]:
        """Get all employees with filtering"""
        query = self.db.query(Employee).options(
            joinedload(Employee.department),
            joinedload(Employee.location)
        )
        
        if is_active is not None:
            query = query.filter(Employee.is_active == is_active)
        
        if department_id:
            query = query.filter(Employee.department_id == department_id)
        
        if location_id:
            query = query.filter(Employee.location_id == location_id)
        
        if is_manager is not None:
            query = query.filter(Employee.is_manager == is_manager)
        
        if search:
            query = query.filter(
                or_(
                    Employee.first_name.ilike(f"%{search}%"),
                    Employee.last_name.ilike(f"%{search}%"),
                    Employee.employee_id.ilike(f"%{search}%"),
                    Employee.email.ilike(f"%{search}%"),
                    Employee.phone.ilike(f"%{search}%")
                )
            )
        
        return query.offset(skip).limit(limit).all()

    async def update_employee(
        self,
        employee_id: int,
        employee_data: EmployeeUpdate,
        current_user_id: int
    ) -> Employee:
        """Update employee"""
        employee = await self.get_employee(employee_id)
        
        # Check email uniqueness if email is being updated
        if employee_data.email and employee_data.email != employee.email:
            existing_email = self.db.query(Employee).filter(
                Employee.email == employee_data.email,
                Employee.id != employee_id,
                Employee.is_active == True
            ).first()
            if existing_email:
                raise ValidationError(f"Employee with email '{employee_data.email}' already exists")

        # Validate department if being updated
        if employee_data.department_id:
            department = self.db.query(Department).filter(
                Department.id == employee_data.department_id,
                Department.is_active == True
            ).first()
            if not department:
                raise ValidationError(f"Department with ID {employee_data.department_id} not found")

        # Validate location if being updated
        if employee_data.location_id:
            location = self.db.query(Location).filter(
                Location.id == employee_data.location_id,
                Location.is_active == True
            ).first()
            if not location:
                raise ValidationError(f"Location with ID {employee_data.location_id} not found")

        update_data = employee_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(employee, field, value)

        self.db.commit()
        self.db.refresh(employee)
        
        logger.info(f"Employee updated: {employee.employee_id} by user {current_user_id}")
        return employee

    async def delete_employee(self, employee_id: int, current_user_id: int) -> bool:
        """Soft delete employee"""
        employee = await self.get_employee(employee_id)
        
        employee.is_active = False
        self.db.commit()
        
        logger.info(f"Employee deleted: {employee.employee_id} by user {current_user_id}")
        return True

    async def get_managers(self, location_id: Optional[int] = None) -> List[Employee]:
        """Get all managers, optionally filtered by location"""
        query = self.db.query(Employee).filter(
            Employee.is_manager == True,
            Employee.is_active == True
        )
        
        if location_id:
            query = query.filter(Employee.location_id == location_id)
        
        return query.all()