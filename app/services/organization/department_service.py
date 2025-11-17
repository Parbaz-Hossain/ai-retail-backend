import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.models.organization.department import Department
from app.models.hr.employee import Employee
from app.schemas.organization.department_schema import DepartmentCreate, DepartmentUpdate

logger = logging.getLogger(__name__)


class DepartmentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- Getters ----------
    async def get_department(self, department_id: int) -> Optional[Department]:
        try:
            result = await self.session.execute(
                select(Department).where(
                    Department.id == department_id,
                    Department.is_deleted == False
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting department {department_id}: {e}")
            return None

    async def get_department_by_name(self, name: str) -> Optional[Department]:
        try:
            result = await self.session.execute(
                select(Department).where(
                    Department.name == name,
                    Department.is_deleted == False
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting department by name: {e}")
            return None

    # ---------- Create / Update / Delete ----------
    async def create_department(self, data: DepartmentCreate, created_by: Optional[int] = None) -> Department:
        try:
            # unique name
            exists = await self.session.execute(
                select(Department.id).where(
                    Department.name == data.name
                ).limit(1)
            )
            if exists.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Department '{data.name}' already exists"
                )

            dept = Department(
                name=data.name,
                description=data.description,
                is_active=True
            )
            self.session.add(dept)
            await self.session.flush()
            await self.session.commit()
            await self.session.refresh(dept)
            logger.info(f"Department created: {dept.name}")
            return dept

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating department: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating department")

    async def update_department(self, department_id: int, data: DepartmentUpdate) -> Optional[Department]:
        try:
            dept = await self.get_department(department_id)
            if not dept or dept.is_deleted:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

            if data.name and data.name != dept.name:
                exists = await self.session.execute(
                    select(Department.id).where(
                        Department.name == data.name,
                        Department.id != department_id,
                        Department.is_deleted == False
                    ).limit(1)
                )
                if exists.scalar_one_or_none() is not None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Department '{data.name}' already exists"
                    )

            for field, value in data.dict(exclude_unset=True).items():
                setattr(dept, field, value)

            dept.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(dept)
            logger.info(f"Department updated: {dept.name}")
            return dept

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating department {department_id}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating department")

    async def delete_department(self, department_id: int, deleted_by: Optional[int] = None) -> bool:
        try:
            dept = await self.get_department(department_id)
            if not dept or dept.is_deleted:
                return False

            # active employees check
            count_result = await self.session.execute(
                select(func.count()).select_from(Employee).where(
                    Employee.department_id == department_id,
                    Employee.is_active == True,
                    Employee.is_deleted == False
                )
            )
            if int(count_result.scalar() or 0) > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete department. It has active employees"
                )

            dept.is_active = False
            dept.is_deleted = True
            dept.updated_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"Department deleted (soft): {dept.name}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting department {department_id}: {e}")
            return False

    # ---------- Listing & Counting ----------
    async def get_departments(
        self,
        page_index: int = 1,
        page_size: int = 100,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get departments with pagination"""
        try:
            query = select(Department).where(Department.is_deleted == False)
            if is_active is not None:
                query = query.where(Department.is_active == is_active)
            if search:
                like = f"%{search}%"
                query = query.where(
                    or_(
                        Department.name.ilike(like),
                        Department.description.ilike(like)
                    )
                )
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total = total_result.scalar() or 0
            
            # Calculate offset and get data
            skip = (page_index - 1) * page_size
            result = await self.session.execute(query.offset(skip).limit(page_size))
            departments = result.scalars().all()
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": departments
            }
        except Exception as e:
            logger.error(f"Error getting departments: {e}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def count_departments(self, search: Optional[str] = None, is_active: Optional[bool] = None) -> int:
        try:
            query = select(func.count(Department.id)).where(Department.is_deleted == False)
            if is_active is not None:
                query = query.where(Department.is_active == is_active)
            if search:
                like = f"%{search}%"
                query = query.where(
                    or_(
                        Department.name.ilike(like),
                        Department.description.ilike(like)
                    )
                )
            result = await self.session.execute(query)
            return int(result.scalar() or 0)
        except Exception as e:
            logger.error(f"Error counting departments: {e}")
            return 0
