from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import time, date
from app.models.hr.shift_type import ShiftType
from app.models.hr.user_shift import UserShift
from app.models.hr.employee import Employee
from app.schemas.hr.shift_schema import ShiftTypeCreate, ShiftTypeUpdate, UserShiftCreate, UserShiftUpdate
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import logger

class ShiftService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # Shift Type Management
    async def create_shift_type(self, shift_data: ShiftTypeCreate, current_user_id: int) -> ShiftType:
        """Create a new shift type"""
        try:
            # Validate time logic
            if shift_data.start_time >= shift_data.end_time:
                raise ValidationError("Start time must be before end time")

            # Check if shift name already exists
            existing = self.db.query(ShiftType).filter(
                ShiftType.name == shift_data.name,
                ShiftType.is_active == True
            ).first()
            if existing:
                raise ValidationError(f"Shift type '{shift_data.name}' already exists")

            shift_type = ShiftType(**shift_data.dict())
            
            self.db.add(shift_type)
            self.db.commit()
            self.db.refresh(shift_type)
            
            logger.info(f"Shift type created: {shift_type.name} by user {current_user_id}")
            return shift_type
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating shift type: {str(e)}")
            raise

    async def get_shift_types(self, is_active: Optional[bool] = None) -> List[ShiftType]:
        """Get all shift types"""
        query = self.db.query(ShiftType)
        
        if is_active is not None:
            query = query.filter(ShiftType.is_active == is_active)
        
        return query.all()

    async def update_shift_type(
        self,
        shift_type_id: int,
        shift_data: ShiftTypeUpdate,
        current_user_id: int
    ) -> ShiftType:
        """Update shift type"""
        shift_type = self.db.query(ShiftType).filter(
            ShiftType.id == shift_type_id,
            ShiftType.is_active == True
        ).first()
        
        if not shift_type:
            raise NotFoundError(f"Shift type with ID {shift_type_id} not found")

        # Validate time logic if times are being updated
        start_time = shift_data.start_time or shift_type.start_time
        end_time = shift_data.end_time or shift_type.end_time
        
        if start_time >= end_time:
            raise ValidationError("Start time must be before end time")

        update_data = shift_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(shift_type, field, value)

        self.db.commit()
        self.db.refresh(shift_type)
        
        logger.info(f"Shift type updated: {shift_type.name} by user {current_user_id}")
        return shift_type

    # User Shift Assignment
    async def assign_shift_to_employee(
        self,
        assignment_data: UserShiftCreate,
        current_user_id: int
    ) -> UserShift:
        """Assign shift to employee"""
        try:
            # Validate employee exists
            employee = self.db.query(Employee).filter(
                Employee.id == assignment_data.employee_id,
                Employee.is_active == True
            ).first()
            if not employee:
                raise ValidationError(f"Employee with ID {assignment_data.employee_id} not found")

            # Validate shift type exists
            shift_type = self.db.query(ShiftType).filter(
                ShiftType.id == assignment_data.shift_type_id,
                ShiftType.is_active == True
            ).first()
            if not shift_type:
                raise ValidationError(f"Shift type with ID {assignment_data.shift_type_id} not found")

            # Check for overlapping active assignments
            existing_active = self.db.query(UserShift).filter(
                UserShift.employee_id == assignment_data.employee_id,
                UserShift.is_active == True,
                UserShift.end_date.is_(None)  # Current active assignment
            ).first()

            if existing_active:
                # End the current assignment
                existing_active.end_date = assignment_data.effective_date
                existing_active.is_active = False

            user_shift = UserShift(**assignment_data.dict())
            
            self.db.add(user_shift)
            self.db.commit()
            self.db.refresh(user_shift)
            
            logger.info(f"Shift assigned: Employee {employee.employee_id} to {shift_type.name} by user {current_user_id}")
            return user_shift
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error assigning shift: {str(e)}")
            raise

    async def get_employee_current_shift(self, employee_id: int) -> Optional[UserShift]:
        """Get employee's current active shift"""
        return self.db.query(UserShift).filter(
            UserShift.employee_id == employee_id,
            UserShift.is_active == True,
            UserShift.end_date.is_(None)
        ).first()

    async def get_employee_shift_history(self, employee_id: int) -> List[UserShift]:
        """Get employee's shift history"""
        return self.db.query(UserShift).filter(
            UserShift.employee_id == employee_id
        ).order_by(UserShift.effective_date.desc()).all()