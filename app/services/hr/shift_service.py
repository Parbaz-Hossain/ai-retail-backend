import logging
from typing import Optional, List
from datetime import date, datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.models.hr.shift_type import ShiftType
from app.models.hr.user_shift import UserShift
from app.models.hr.employee import Employee
from app.schemas.hr.shift_schema import ShiftTypeCreate, ShiftTypeUpdate, UserShiftCreate, UserShiftUpdate
from app.utils.validators.validation_utils import is_valid_shift

logger = logging.getLogger(__name__)


class ShiftService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- Shift Type Management ----------
    async def create_shift_type(self, data: ShiftTypeCreate, current_user_id: int) -> ShiftType:
        try:
            if not is_valid_shift(data.start_time, data.end_time):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Start time must be before end time"
                )

            # unique name
            exists = await self.session.execute(
                select(ShiftType.id).where(ShiftType.name == data.name, ShiftType.is_active == True).limit(1)
            )
            if exists.scalar_one_or_none() is not None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Shift type '{data.name}' already exists")

            shift_type = ShiftType(**data.dict())
            self.session.add(shift_type)
            await self.session.flush()
            await self.session.commit()
            await self.session.refresh(shift_type)

            logger.info(f"Shift type created: {shift_type.name} by user {current_user_id}")
            return shift_type

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating shift type: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating shift type")

    async def get_shift_types(self, is_active: Optional[bool] = None) -> List[ShiftType]:
        try:
            query = select(ShiftType)
            if is_active is not None:
                query = query.where(ShiftType.is_active == is_active)
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting shift types: {e}")
            return []
        
    async def get_shift_type(self, shift_type_id: int) -> Optional[ShiftType]:
        try:
            result = await self.session.execute(
                select(ShiftType).where(
                    ShiftType.id == shift_type_id,
                    ShiftType.is_active == True
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting location {shift_type_id}: {e}")
            return None

    async def update_shift_type(self, shift_type_id: int, data: ShiftTypeUpdate, current_user_id: int) -> ShiftType:
        try:
            result = await self.session.execute(
                select(ShiftType).where(ShiftType.id == shift_type_id, ShiftType.is_active == True)
            )
            shift_type = result.scalar_one_or_none()
            if not shift_type:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift type not found")

            # time validation using existing values as fallback
            if not is_valid_shift(data.start_time, data.end_time):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Start time must be before end time"
                )

            for field, value in data.dict(exclude_unset=True).items():
                setattr(shift_type, field, value)

            if hasattr(shift_type, "updated_at"):
                shift_type.updated_at = datetime.utcnow()

            await self.session.commit()
            await self.session.refresh(shift_type)
            logger.info(f"Shift type updated: {shift_type.name} by user {current_user_id}")
            return shift_type

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating shift type {shift_type_id}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating shift type")

    # ---------- User Shift Assignment ----------
    async def assign_shift_to_employee(self, data: UserShiftCreate, current_user_id: int) -> UserShift:
        try:
            # validate employee
            emp_res = await self.session.execute(
                select(Employee).where(Employee.id == data.employee_id, Employee.is_active == True)
            )
            employee = emp_res.scalar_one_or_none()
            if not employee:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Employee with ID {data.employee_id} not found")

            # validate shift type
            st_res = await self.session.execute(
                select(ShiftType).where(ShiftType.id == data.shift_type_id, ShiftType.is_active == True)
            )
            shift_type = st_res.scalar_one_or_none()
            if not shift_type:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Shift type with ID {data.shift_type_id} not found")

            # close any current active assignment
            current_res = await self.session.execute(
                select(UserShift).where(
                    UserShift.employee_id == data.employee_id,
                    UserShift.is_active == True,
                    UserShift.end_date.is_(None)
                )
            )
            current_active = current_res.scalar_one_or_none()
            if current_active:
                current_active.end_date = data.effective_date
                current_active.is_active = False

            user_shift = UserShift(**data.dict())
            self.session.add(user_shift)

            await self.session.commit()
            await self.session.refresh(user_shift, attribute_names=["shift_type"])

            logger.info(f"Shift assigned: Employee {employee.employee_id} -> {shift_type.name} by user {current_user_id}")
            return user_shift

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error assigning shift: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error assigning shift")

    # ---------- Queries ----------        
    async def get_employee_current_shift(self, employee_id: int) -> Optional[UserShift]:
        try:
            today = date.today()
            result = await self.session.execute(
                select(UserShift)
                .options(
                    selectinload(UserShift.shift_type)
                )
                .where(
                    UserShift.employee_id == employee_id,
                    UserShift.is_active == True,
                    UserShift.effective_date <= today,
                    or_(
                        UserShift.end_date.is_(None),
                        UserShift.end_date >= today
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting current shift for employee {employee_id}: {e}")
            return None

    async def get_employee_shift_history(self, employee_id: int) -> List[UserShift]:
        try:
            result = await self.session.execute(
                select(UserShift)
                .options(
                    selectinload(UserShift.shift_type)
                )
                .where(UserShift.employee_id == employee_id)
                .order_by(UserShift.effective_date.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting shift history for employee {employee_id}: {e}")
            return []
