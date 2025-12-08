import calendar
import logging
from typing import Any, Dict, Optional, List
from datetime import date, datetime
from app.models.hr.offday import Offday
from app.models.shared.enums import DayOfWeek, OffdayType
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import selectinload

from app.models.hr.shift_type import ShiftType
from app.models.hr.user_shift import UserShift
from app.models.hr.employee import Employee
from app.models.organization.location import Location
from app.schemas.hr.shift_schema import BulkShiftAndOffdayAssignment, BulkShiftAndOffdayResult, BulkShiftAssignmentResult, BulkUserShiftCreate, EmployeeAssignmentResult, EmployeeShiftDetail, EmployeeShiftSummary, ShiftTypeCreate, ShiftTypeUpdate, UserShiftCreate, UserShiftUpdate
from app.utils.validators.validation_utils import is_valid_shift
from app.services.auth.user_service import UserService

logger = logging.getLogger(__name__)


class ShiftService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(session)

    # Day of week mapping
    DAY_MAP = {
        DayOfWeek.MONDAY: 0,
        DayOfWeek.TUESDAY: 1,
        DayOfWeek.WEDNESDAY: 2,
        DayOfWeek.THURSDAY: 3,
        DayOfWeek.FRIDAY: 4,
        DayOfWeek.SATURDAY: 5,
        DayOfWeek.SUNDAY: 6
    }

    def _get_all_dates_for_day_of_week(self, year: int, month: int, day_of_week: DayOfWeek) -> List[date]:
        """Get all dates in a month that fall on a specific day of week"""
        target_weekday = self.DAY_MAP[day_of_week]
        dates = []
        
        # Get the number of days in the month
        _, num_days = calendar.monthrange(year, month)
        
        # Check each day in the month
        for day in range(1, num_days + 1):
            current_date = date(year, month, day)
            if current_date.weekday() == target_weekday:
                dates.append(current_date)
        
        return dates

    # region Shift Type Management 

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

    async def get_shift_types(
        self,
        page_index: int = 1,
        page_size: int = 100,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get paginated shift types with filtering"""
        try:
            conditions = []
            
            if is_active is not None:
                conditions.append(ShiftType.is_active == is_active)
            
            # Get total count
            total_count = await self.session.scalar(
                select(func.count(ShiftType.id)).where(*conditions)
            )
            
            # Calculate offset
            skip = (page_index - 1) * page_size
            
            # Get paginated data
            shift_types = await self.session.scalars(
                select(ShiftType)
                .where(*conditions)
                .offset(skip)
                .limit(page_size)
            )
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": shift_types.all()
            }
            
        except Exception as e:
            logger.error(f"Error getting shift types: {e}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }
        
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

# endregion


    # region User Shift Management

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

    # ---------- Bulk User Shift Assignment ----------
    async def bulk_assign_shifts_to_employees(
        self, 
        data: BulkUserShiftCreate, 
        current_user_id: int
    ) -> BulkShiftAssignmentResult:
        """
        Assign shifts to multiple employees at once.
        - Validates all employees and shift type
        - Deletes any existing shifts with the same effective_date (permanent deletion)
        - Creates new shift assignments
        """
        successful = 0
        failed = 0
        results = []
        
        try:
            # Validate shift type first
            st_res = await self.session.execute(
                select(ShiftType).where(
                    ShiftType.id == data.shift_type_id, 
                    ShiftType.is_active == True
                )
            )
            shift_type = st_res.scalar_one_or_none()
            if not shift_type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Shift type with ID {data.shift_type_id} not found or inactive"
                )
            
            # Validate all employees exist and are active
            emp_res = await self.session.execute(
                select(Employee).where(
                    Employee.id.in_(data.employee_ids),
                    Employee.is_active == True
                )
            )
            valid_employees = {emp.id: emp for emp in emp_res.scalars().all()}
            
            # Check which employees are invalid
            invalid_employee_ids = set(data.employee_ids) - set(valid_employees.keys())
            if invalid_employee_ids:
                for emp_id in invalid_employee_ids:
                    results.append({
                        "employee_id": emp_id,
                        "status": "failed",
                        "error": "Employee not found or inactive"
                    })
                    failed += 1
            
            # Process valid employees
            for employee_id in valid_employees.keys():
                try:
                    employee = valid_employees[employee_id]
                    
                    # Delete any existing shifts
                    existing_shifts_result = await self.session.execute(
                            select(UserShift).where(UserShift.employee_id == employee_id)
                        )
                    existing_shifts = existing_shifts_result.scalars().all()
                        
                    # Check each shift for overlap and delete if necessary
                    for existing_shift in existing_shifts:
                        existing_start = existing_shift.effective_date
                        existing_end = existing_shift.end_date
                        
                        new_start = data.effective_date
                        new_end = data.end_date
                        
                        # Check for overlap
                        has_overlap = False
                        
                        if new_end is None:
                            if existing_end is None:
                                has_overlap = existing_start <= new_start
                            else:
                                has_overlap = existing_end >= new_start
                        else:
                            if existing_end is None:
                                has_overlap = existing_start <= new_end
                            else:
                                has_overlap = (existing_start <= new_end) and (new_start <= existing_end)
                        
                        if has_overlap:
                            await self.session.execute(
                                delete(UserShift).where(UserShift.id == existing_shift.id)
                            )
                                        
                    # Create new shift assignment
                    new_shift = UserShift(
                        employee_id=employee_id,
                        shift_type_id=data.shift_type_id,
                        effective_date=data.effective_date,
                        end_date=data.end_date,
                        deduction_amount=data.deduction_amount or 0,
                        is_active=True
                    )
                    self.session.add(new_shift)
                    
                    results.append({
                        "employee_id": employee_id,
                        "employee_code": employee.employee_id,
                        "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
                        "status": "success",
                        "shift_type": shift_type.name,
                        "effective_date": data.effective_date.isoformat()
                    })
                    successful += 1
                    
                except Exception as e:
                    logger.error(f"Error assigning shift to employee {employee_id}: {e}")
                    results.append({
                        "employee_id": employee_id,
                        "status": "failed",
                        "error": str(e)
                    })
                    failed += 1
            
            # Commit all changes
            await self.session.commit()
            
            logger.info(
                f"Bulk shift assignment completed by user {current_user_id}: "
                f"{successful} successful, {failed} failed out of {len(data.employee_ids)} total"
            )
            
            return BulkShiftAssignmentResult(
                total_requested=len(data.employee_ids),
                successful=successful,
                failed=failed,
                results=results
            )
            
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error in bulk shift assignment: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"Error in bulk shift assignment: {str(e)}"
            )
        
    # ---------- Bulk Shift and Offday Assignment ----------
    async def bulk_assign_shifts_and_offdays(
        self,
        data: BulkShiftAndOffdayAssignment,
        current_user_id: int
    ) -> BulkShiftAndOffdayResult:
        """
        Assign shifts and offdays to multiple employees at once.
        - Assigns shift for the entire month (start to end date)
        - Creates offdays for all occurrences of the specified day in the month
        - Deletes overlapping existing shifts
        - Deletes existing offdays for the month before creating new ones
        """
        successful = 0
        failed = 0
        results = []
        
        try:
            # Determine year and month
            now = datetime.now()
            year = data.year if data.year else now.year
            month = data.month if data.month else now.month
            
            # Calculate month start and end dates
            _, last_day = calendar.monthrange(year, month)
            effective_date = date(year, month, 1)
            end_date = date(year, month, last_day)
            
            # Collect all unique employee IDs and shift type IDs
            employee_ids = [emp.employee_id for emp in data.employees]
            shift_type_ids = list(set([emp.shift_type_id for emp in data.employees]))
            
            # Validate all employees exist and are active
            emp_res = await self.session.execute(
                select(Employee).where(
                    Employee.id.in_(employee_ids),
                    Employee.is_active == True
                )
            )
            valid_employees = {emp.id: emp for emp in emp_res.scalars().all()}
            
            # Validate all shift types exist and are active
            st_res = await self.session.execute(
                select(ShiftType).where(
                    ShiftType.id.in_(shift_type_ids),
                    ShiftType.is_active == True
                )
            )
            valid_shift_types = {st.id: st for st in st_res.scalars().all()}
            
            # Process each employee assignment
            for emp_assignment in data.employees:
                employee_id = emp_assignment.employee_id
                shift_type_id = emp_assignment.shift_type_id
                off_day = emp_assignment.off_day
                
                result = EmployeeAssignmentResult(
                    employee_id=employee_id,
                    status="failed"
                )
                
                try:
                    # Validate employee
                    if employee_id not in valid_employees:
                        result.error = "Employee not found or inactive"
                        results.append(result)
                        failed += 1
                        continue
                    
                    employee = valid_employees[employee_id]
                    result.employee_code = employee.employee_id
                    result.employee_name = f"{employee.first_name} {employee.last_name}".strip()
                    
                    # Validate shift type
                    if shift_type_id not in valid_shift_types:
                        result.error = f"Shift type with ID {shift_type_id} not found or inactive"
                        results.append(result)
                        failed += 1
                        continue
                    
                    shift_type = valid_shift_types[shift_type_id]
                    
                    # ===== SHIFT ASSIGNMENT =====
                    # Delete overlapping shifts
                    existing_shifts_result = await self.session.execute(
                        select(UserShift).where(UserShift.employee_id == employee_id)
                    )
                    existing_shifts = existing_shifts_result.scalars().all()
                    
                    for existing_shift in existing_shifts:
                        existing_start = existing_shift.effective_date
                        existing_end = existing_shift.end_date
                        
                        # Check for overlap with the new month assignment
                        has_overlap = False
                        if existing_end is None:
                            has_overlap = existing_start <= end_date
                        else:
                            has_overlap = (existing_start <= end_date) and (effective_date <= existing_end)
                        
                        if has_overlap:
                            await self.session.execute(
                                delete(UserShift).where(UserShift.id == existing_shift.id)
                            )
                    
                    # Create new shift assignment for the month
                    new_shift = UserShift(
                        employee_id=employee_id,
                        shift_type_id=shift_type_id,
                        effective_date=effective_date,
                        end_date=end_date,
                        deduction_amount=0,
                        is_active=True
                    )
                    self.session.add(new_shift)
                    result.shift_assigned = True
                    
                    # ===== OFFDAY ASSIGNMENT =====
                    # Delete existing offdays for this employee in this month
                    await self.session.execute(
                        delete(Offday).where(
                            Offday.employee_id == employee_id,
                            Offday.year == year,
                            Offday.month == month
                        )
                    )
                    
                    # Get all dates for the specified day of week in this month
                    offday_dates = self._get_all_dates_for_day_of_week(year, month, off_day)
                    
                    # Create offday records
                    for offday_date in offday_dates:
                        offday = Offday(
                            employee_id=employee_id,
                            year=year,
                            month=month,
                            offday_date=offday_date,
                            offday_type=OffdayType.WEEKEND,
                            description=f"Weekly off day - {off_day.value}",
                            is_active=True
                        )
                        self.session.add(offday)
                    
                    result.offdays_created = len(offday_dates)
                    result.status = "success"
                    results.append(result)
                    successful += 1
                    
                    logger.info(
                        f"Assigned shift {shift_type.name} and {len(offday_dates)} offdays "
                        f"to employee {employee.employee_id} for {year}-{month:02d}"
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing employee {employee_id}: {e}")
                    result.error = str(e)
                    results.append(result)
                    failed += 1
            
            # Commit all changes
            await self.session.commit()
            
            logger.info(
                f"Bulk shift and offday assignment completed by user {current_user_id}: "
                f"{successful} successful, {failed} failed out of {len(data.employees)} total"
            )
            
            return BulkShiftAndOffdayResult(
                total_requested=len(data.employees),
                successful=successful,
                failed=failed,
                year=year,
                month=month,
                effective_date=effective_date,
                end_date=end_date,
                results=results
            )
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error in bulk shift and offday assignment: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error in bulk shift and offday assignment: {str(e)}"
            )

    # ---------- User Shift Update ----------
    async def update_user_shift(self, user_shift_id: int, data: UserShiftUpdate, current_user_id: int) -> UserShift:
        """Update an existing user shift assignment"""
        try:
            result = await self.session.execute(
                select(UserShift)
                .options(selectinload(UserShift.shift_type))
                .where(UserShift.id == user_shift_id)
            )
            user_shift = result.scalar_one_or_none()
            
            if not user_shift:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail="User shift not found"
                )

            # Update fields
            for field, value in data.dict(exclude_unset=True).items():
                setattr(user_shift, field, value)

            if hasattr(user_shift, "updated_at"):
                user_shift.updated_at = datetime.utcnow()

            await self.session.commit()
            await self.session.refresh(user_shift)
            
            logger.info(f"User shift {user_shift_id} updated by user {current_user_id}")
            return user_shift

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating user shift {user_shift_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Error updating user shift"
            )

    async def get_employee_shifts(
        self,
        page_index: int = 1,
        page_size: int = 100,
        search: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        is_active: Optional[bool] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get employee shifts grouped by employee.
        Shows one row per employee with their current shift and total shift count.
        """
        try:
            
            # Build conditions
            conditions = []
            
            if is_active is not None:
                conditions.append(Employee.is_active == is_active)
            
            # Date range for shifts
            shift_conditions = []
            if start_date:
                shift_conditions.append(UserShift.effective_date >= start_date)
            if end_date:
                shift_conditions.append(UserShift.effective_date <= end_date)
            
            # Base query to get distinct employees with shifts
            query = (
                select(Employee)
                .join(UserShift, Employee.id == UserShift.employee_id)
                .options(
                    selectinload(Employee.department)
                )
                .distinct()
            )

            # Location manager restriction
            role_name = await self.user_service.get_specific_role_name_by_user(user_id, "location_manager")
            if role_name:
                loc_res = await self.session.execute(
                    select(Location).where(Location.manager_id == user_id)
                )
                loc_ids = loc_res.scalars().all()
                if loc_ids:
                    conditions.append(Employee.location_id.in_(loc_ids))
            
            # Apply shift date filters
            if shift_conditions:
                query = query.where(*shift_conditions)
            
            # Search filter
            if search:
                search_pattern = f"%{search}%"
                query = query.where(
                    or_(
                        Employee.first_name.ilike(search_pattern),
                        Employee.last_name.ilike(search_pattern),
                        Employee.employee_id.ilike(search_pattern)
                    )
                )
            
            # Apply employee conditions
            if conditions:
                query = query.where(*conditions)
            
            # Get total count of unique employees
            count_subquery = query.subquery()
            total_count = await self.session.scalar(
                select(func.count()).select_from(count_subquery)
            )
            
            # Calculate offset
            skip = (page_index - 1) * page_size
            
            # Get paginated employees
            query = query.order_by(Employee.first_name).offset(skip).limit(page_size)
            result = await self.session.execute(query)
            employees = result.scalars().all()
            
            # Build response data
            data = []
            today = date.today()
            
            for employee in employees:
                # Get current shift
                current_shift_result = await self.session.execute(
                    select(UserShift)
                    .options(selectinload(UserShift.shift_type))
                    .where(
                        UserShift.employee_id == employee.id,
                        UserShift.is_active == True,
                        UserShift.effective_date <= today,
                        or_(
                            UserShift.end_date.is_(None),
                            UserShift.end_date >= today
                        )
                    )
                )
                current_shift = current_shift_result.scalar_one_or_none()
                
                # Get total shift count
                shift_count_conditions = [UserShift.employee_id == employee.id]
                if shift_conditions:
                    shift_count_conditions.extend(shift_conditions)
                
                total_shifts = await self.session.scalar(
                    select(func.count(UserShift.id))
                    .where(*shift_count_conditions)
                )
                
                # Get latest shift date
                latest_date_result = await self.session.execute(
                    select(func.max(UserShift.effective_date))
                    .where(*shift_count_conditions)
                )
                latest_date = latest_date_result.scalar()
                
                # Build summary
                employee_data = EmployeeShiftSummary(
                    employee_id=employee.id,
                    employee_code=employee.employee_id,
                    employee_name=f"{employee.first_name} {employee.last_name}".strip(),
                    department=getattr(employee.department, 'name', None) if hasattr(employee, 'department') else None,
                    current_shift=current_shift,
                    total_shift_changes=total_shifts or 0,
                    latest_effective_date=latest_date
                )
                data.append(employee_data)
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": data
            }
            
        except Exception as e:
            logger.error(f"Error getting grouped employee shifts: {e}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def get_employee_shift_details(self, employee_id: int) -> Optional[EmployeeShiftDetail]:
        """Get detailed shift information for a specific employee"""
        try:
            # Get employee
            emp_result = await self.session.execute(
                select(Employee)
                .options(selectinload(Employee.department))
                .where(Employee.id == employee_id)
            )
            employee = emp_result.scalar_one_or_none()
            
            if not employee:
                return None
            
            # Get current shift
            today = date.today()
            current_shift_result = await self.session.execute(
                select(UserShift)
                .options(selectinload(UserShift.shift_type))
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
            current_shift = current_shift_result.scalar_one_or_none()
            
            # Get all shift history
            history_result = await self.session.execute(
                select(UserShift)
                .options(selectinload(UserShift.shift_type))
                .where(UserShift.employee_id == employee_id)
                .order_by(UserShift.effective_date.desc())
            )
            shift_history = history_result.scalars().all()
            
            return EmployeeShiftDetail(
                employee_id=employee.id,
                employee_code=employee.employee_id,
                employee_name=f"{employee.first_name} {employee.last_name}".strip(),
                department=getattr(employee.department, 'name', None) if hasattr(employee, 'department') else None,
                current_shift=current_shift,
                shift_history=list(shift_history),
                total_shifts=len(shift_history)
            )
            
        except Exception as e:
            logger.error(f"Error getting employee shift detail: {e}")
            return None
        
    # endregion