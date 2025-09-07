import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.models.hr.employee import Employee
from app.models.organization.department import Department
from app.models.organization.location import Location
from app.schemas.hr.employee_schema import EmployeeCreate, EmployeeUpdate

logger = logging.getLogger(__name__)


class EmployeeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- Helpers ----------
    async def _generate_employee_id(self) -> str:
        prefix = "EMP"
        timestamp = datetime.utcnow().strftime("%y%m")
        result = await self.session.execute(
            select(func.count()).select_from(Employee).where(
                Employee.employee_id.like(f"{prefix}{timestamp}%")
            )
        )
        count = int(result.scalar() or 0)
        return f"{prefix}{timestamp}{count + 1:04d}"

    # ---------- Create / Update / Delete ----------
    async def create_employee(self, data: EmployeeCreate, current_user_id: int) -> Employee:
        try:
            # validate department
            dep_res = await self.session.execute(
                select(Department.id).where(
                    Department.id == data.department_id,
                    Department.is_active == True
                )
            )
            if dep_res.scalar_one_or_none() is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Department with ID {data.department_id} not found")

            # validate location
            loc_res = await self.session.execute(
                select(Location.id).where(
                    Location.id == data.location_id,
                    Location.is_active == True
                )
            )
            if loc_res.scalar_one_or_none() is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Location with ID {data.location_id} not found")

            # unique email (active)
            email_res = await self.session.execute(
                select(Employee.id).where(
                    Employee.email == data.email,
                    Employee.is_active == True
                ).limit(1)
            )
            if email_res.scalar_one_or_none() is not None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Employee with email '{data.email}' already exists")

            employee_id = await self._generate_employee_id()
            employee = Employee(employee_id=employee_id, **data.dict())

            self.session.add(employee)
            await self.session.flush()
            await self.session.commit()
            await self.session.refresh(employee, attribute_names=["department", "location"])

            logger.info(f"Employee created: {employee.employee_id} - {employee.first_name} {employee.last_name} by user {current_user_id}")
            return employee

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating employee: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating employee")

    async def update_employee(self, employee_id: int, data: EmployeeUpdate, current_user_id: int) -> Employee:
        try:
            employee = await self.get_employee(employee_id)
            if not employee:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

            # email uniqueness when changed
            if data.email and data.email != employee.email:
                email_res = await self.session.execute(
                    select(Employee.id).where(
                        Employee.email == data.email,
                        Employee.id != employee_id,
                        Employee.is_active == True
                    ).limit(1)
                )
                if email_res.scalar_one_or_none() is not None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                        detail=f"Employee with email '{data.email}' already exists")

            # validate department if provided
            if data.department_id:
                dep_res = await self.session.execute(
                    select(Department.id).where(
                        Department.id == data.department_id,
                        Department.is_active == True
                    )
                )
                if dep_res.scalar_one_or_none() is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                        detail=f"Department with ID {data.department_id} not found")

            # validate location if provided
            if data.location_id:
                loc_res = await self.session.execute(
                    select(Location.id).where(
                        Location.id == data.location_id,
                        Location.is_active == True
                    )
                )
                if loc_res.scalar_one_or_none() is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                        detail=f"Location with ID {data.location_id} not found")

            for field, value in data.dict(exclude_unset=True).items():
                setattr(employee, field, value)

            if hasattr(employee, "updated_at"):
                employee.updated_at = datetime.utcnow()

            await self.session.commit()
            await self.session.refresh(employee)

            logger.info(f"Employee updated: {employee.employee_id} by user {current_user_id}")
            return employee

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating employee {employee_id}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating employee")

    async def delete_employee(self, employee_id: int, current_user_id: int) -> bool:
        try:
            employee = await self.get_employee(employee_id)
            if not employee:
                return False

            employee.is_active = False
            employee.is_deleted = True
            if hasattr(employee, "updated_at"):
                employee.updated_at = datetime.utcnow()

            await self.session.commit()
            logger.info(f"Employee deleted: {employee.employee_id} by user {current_user_id}")
            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting employee {employee_id}: {e}")
            return False

    # ---------- Getters ----------
    async def get_employee(self, employee_id: int) -> Optional[Employee]:
        try:
            result = await self.session.execute(
                select(Employee)
                .options(
                    selectinload(Employee.department),
                    selectinload(Employee.location),
                )
                .where(
                    Employee.id == employee_id,
                    Employee.is_active == True
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting employee {employee_id}: {e}")
            return None

    # ---------- Listing ----------
    async def get_employees(
        self,
        page_index: int = 1,
        page_size: int = 100,
        department_id: Optional[int] = None,
        location_id: Optional[int] = None,
        is_manager: Optional[bool] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get paginated list of employees with filtering"""
        try:
            conditions = []
            
            if is_active is not None:
                conditions.append(Employee.is_active == is_active)
            if department_id:
                conditions.append(Employee.department_id == department_id)
            if location_id:
                conditions.append(Employee.location_id == location_id)
            if is_manager is not None:
                conditions.append(Employee.is_manager == is_manager)
            if search:
                like = f"%{search}%"
                conditions.append(
                    or_(
                        Employee.first_name.ilike(like),
                        Employee.last_name.ilike(like),
                        Employee.employee_id.ilike(like),
                        Employee.email.ilike(like),
                        Employee.phone.ilike(like),
                    )
                )

            # Get total count
            total_count = await self.session.scalar(
                select(func.count(Employee.id)).where(*conditions)
            )

            # Calculate offset
            skip = (page_index - 1) * page_size

            # Get paginated data
            employees = await self.session.scalars(
                select(Employee)
                .options(
                    selectinload(Employee.department),
                    selectinload(Employee.location),
                )
                .where(*conditions)
                .offset(skip)
                .limit(page_size)
            )

            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": employees.all()
            }

        except Exception as e:
            logger.error(f"Error getting employees: {e}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    # ---------- Quick helpers ----------
    async def get_managers(self, location_id: Optional[int] = None) -> List[Employee]:
        try:
            query = (
                select(Employee)
                .options(
                    selectinload(Employee.department),
                    selectinload(Employee.location),
                )
                .where(
                    Employee.is_manager.is_(True),
                    Employee.is_active.is_(True),
                )
            )
            if location_id:
                query = query.where(Employee.location_id == location_id)

            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting managers: {e}")
            return []
