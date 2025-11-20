import logging
from typing import Any, Optional, List, Dict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from app.models.hr.attendance import Attendance
from app.models.hr.employee import Employee
from app.models.hr.user_shift import UserShift
from app.models.hr.shift_type import ShiftType
from app.models.hr.holiday import Holiday
from app.models.hr.offday import Offday
from app.models.hr.ticket import Ticket
from app.models.organization.location import Location
from app.models.shared.enums import AttendanceStatus
from app.schemas.hr.attendance_schema import AttendanceCreate, AttendanceResponse
from app.schemas.hr.ticket_schema import TicketCreate
from app.services.hr.ticket_service import TicketService
from app.services.auth.user_service import UserService

logger = logging.getLogger(__name__)

def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:  # naive → assume UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def is_night_shift(shift_start_time, shift_end_time) -> bool:
    """Check if this is a night shift (crosses midnight)"""
    return shift_end_time < shift_start_time

def get_shift_dates_and_times(attendance_date: date, shift_start_time, shift_end_time, check_in_time: datetime = None, check_out_time: datetime = None):
    """
    Calculate proper shift start/end datetimes for both day and night shifts
    Returns: (shift_start_datetime, shift_end_datetime, effective_attendance_date)
    """
    
    if is_night_shift(shift_start_time, shift_end_time):
        # Night shift: starts on attendance_date, ends on next day
        shift_start = datetime.combine(attendance_date, shift_start_time).replace(tzinfo=timezone.utc)
        shift_end = datetime.combine(attendance_date + timedelta(days=1), shift_end_time).replace(tzinfo=timezone.utc)
        
        # For check-out on the next day, we need to find the attendance record from previous day
        if check_out_time and not check_in_time:
            # This is a check-out operation on the day after shift started
            # The attendance record should be from the previous day
            effective_attendance_date = attendance_date - timedelta(days=1)
            shift_start = datetime.combine(effective_attendance_date, shift_start_time).replace(tzinfo=timezone.utc)
            shift_end = datetime.combine(attendance_date, shift_end_time).replace(tzinfo=timezone.utc)
        else:
            effective_attendance_date = attendance_date
            
    else:
        # Day shift: starts and ends on the same day
        shift_start = datetime.combine(attendance_date, shift_start_time).replace(tzinfo=timezone.utc)
        shift_end = datetime.combine(attendance_date, shift_end_time).replace(tzinfo=timezone.utc)
        effective_attendance_date = attendance_date
    
    return shift_start, shift_end, effective_attendance_date

class AttendanceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.ticket_service = TicketService(session)
        self.user_service = UserService(session)

    # region Attendance Helper Methods
    async def _check_holiday(self, attendance_date: date) -> bool:
        """Check if the date is a company holiday"""
        holiday_res = await self.session.execute(
            select(Holiday).where(
                Holiday.date == attendance_date, 
                Holiday.is_active == True
            )
        )
        return holiday_res.scalars().first() is not None

    async def _check_weekend_offday(self, employee_id: int, attendance_date: date) -> bool:
        """Check if the date is a weekend/offday for the employee"""
        offday_res = await self.session.execute(
            select(Offday).where(
                Offday.employee_id == employee_id,
                Offday.offday_date == attendance_date,
                Offday.is_active == True
            )
        )
        return offday_res.scalars().first() is not None

    async def _get_employee_shift(self, employee_id: int, attendance_date: date):
        """Get employee's shift information for the given date"""
        shift_res = await self.session.execute(
            select(UserShift)
            .options(selectinload(UserShift.shift_type))
            .join(ShiftType)
            .where(
                UserShift.employee_id == employee_id,
                UserShift.is_active == True,
                UserShift.effective_date <= attendance_date,
                ((UserShift.end_date.is_(None)) | (UserShift.end_date >= attendance_date))
            )
        )
        return shift_res.scalars().first()

    async def _find_attendance_for_checkout(self, employee_id: int, attendance_date: date, check_out_time: datetime):
        """
        Find the correct attendance record for check-out, handling night shifts
        """
        # First try to find attendance for the current date
        current_day_res = await self.session.execute(
            select(Attendance).options(selectinload(Attendance.employee)).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date == attendance_date
            )
        )
        current_day_attendance = current_day_res.scalars().first()
        
        if current_day_attendance and current_day_attendance.check_in_time and not current_day_attendance.check_out_time:
            return current_day_attendance
        
        # If not found or already checked out, look for previous day (night shift scenario)
        previous_date = attendance_date - timedelta(days=1)
        previous_day_res = await self.session.execute(
            select(Attendance).options(selectinload(Attendance.employee)).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date == previous_date,
                Attendance.check_in_time.isnot(None),
                Attendance.check_out_time.is_(None)
            )
        )
        previous_day_attendance = previous_day_res.scalars().first()
        
        if previous_day_attendance:
            # Verify this is indeed a night shift by checking the shift times
            user_shift = await self._get_employee_shift(employee_id, previous_date)
            if user_shift and is_night_shift(user_shift.shift_type.start_time, user_shift.shift_type.end_time):
                # Calculate expected shift end time for previous day's night shift
                _, shift_end, _ = get_shift_dates_and_times(
                    previous_date, 
                    user_shift.shift_type.start_time, 
                    user_shift.shift_type.end_time
                )
                
                # Check if check_out_time is reasonable for this shift (within 4 hours of expected end)
                time_diff = abs((check_out_time - shift_end).total_seconds() / 3600)
                if time_diff <= 4:  # Within 4 hours of expected shift end
                    return previous_day_attendance
        
        return None

    async def _check_existing_ticket(self, employee_id: int, attendance_date: date, ticket_type: str) -> bool:
        """Check if a ticket already exists for this employee on this date with this type"""
        result = await self.session.execute(
            select(Ticket).where(
                Ticket.employee_id == employee_id,
                func.date(Ticket.created_at) == attendance_date,
                Ticket.ticket_type == ticket_type
            )
        )
        return result.scalar_one_or_none() is not None

    async def _create_late_ticket(self, employee_id: int, user_shift: UserShift, attendance_date: date):
        """Create a ticket for late attendance"""
        try:
            # Check if ticket already exists for this date
            if await self._check_existing_ticket(employee_id, attendance_date, "LATE"):
                logger.info(f"Late ticket already exists for employee {employee_id} on {attendance_date}")
                return
            
            # Get deduction amount from user_shift
            deduction_amount = user_shift.deduction_amount or Decimal("0.00")
            
            # Create ticket
            ticket_data = TicketCreate(
                employee_id=employee_id,
                ticket_type="LATE",
                deduction_amount=deduction_amount
            )
            
            await self.ticket_service.create_ticket(ticket_data)
            logger.info(f"Late ticket created for employee {employee_id} - Amount: {deduction_amount}")
            
        except Exception as e:
            logger.error(f"Error creating late ticket: {e}")
            # Don't raise exception, just log it to not block attendance marking

    async def _create_absent_ticket(self, employee_id: int, attendance_date: date):
        """Create a ticket for absent attendance with one day salary deduction"""
        try:
            # Check if ticket already exists for this date
            if await self._check_existing_ticket(employee_id, attendance_date, "ABSENT"):
                logger.info(f"Absent ticket already exists for employee {employee_id} on {attendance_date}")
                return
            
            # Get employee details to calculate one day salary
            emp_result = await self.session.execute(
                select(Employee).where(Employee.id == employee_id)
            )
            employee = emp_result.scalar_one_or_none()
            
            if not employee:
                logger.error(f"Employee {employee_id} not found for absent ticket")
                return
            
            # Calculate one day salary
            monthly_salary = (
                (employee.basic_salary or Decimal('0')) +
                (employee.housing_allowance or Decimal('0')) +
                (employee.transport_allowance or Decimal('0'))
            )
            one_day_salary = round(monthly_salary / 30, 2)
            
            # Create ticket
            ticket_data = TicketCreate(
                employee_id=employee_id,
                ticket_type="ABSENT",
                deduction_amount=one_day_salary
            )
            
            await self.ticket_service.create_ticket(ticket_data)
            logger.info(f"Absent ticket created for employee {employee_id} - Amount: {one_day_salary}")
            
        except Exception as e:
            logger.error(f"Error creating absent ticket: {e}")
            
    # endregion

    # ---------- Mark Attendance ---------
    async def mark_attendance(self, data) -> AttendanceResponse:
        try:
            # Validate employee
            emp_res = await self.session.execute(
                select(Employee).where(Employee.id == data.employee_id, Employee.is_active == True)
            )
            employee = emp_res.scalar_one_or_none()
            if not employee:
                raise HTTPException(status_code=400, detail="Employee not found")

            # Normalize times
            check_in_time = ensure_utc(data.check_in_time)
            check_out_time = ensure_utc(data.check_out_time)

            # ========== CHECK-OUT LOGIC ==========
            if check_out_time and not check_in_time:
                # This is a check-out operation
                existing = await self._find_attendance_for_checkout(data.employee_id, data.attendance_date, check_out_time)
                
                if not existing:
                    raise HTTPException(status_code=400, detail="No check-in record found for check-out. Please check-in first.")
                
                if existing.check_out_time:
                    raise HTTPException(status_code=400, detail="Already checked out for this shift.")

                # Get shift information for the attendance date (not current date)
                user_shift = await self._get_employee_shift(data.employee_id, existing.attendance_date)
                
                if not user_shift:
                    # If no shift found, just record the check-out without shift calculations
                    existing.check_out_time = check_out_time
                    existing.bio_check_out = data.bio_check_out or False
                    
                    if existing.check_in_time:
                        duration = check_out_time - ensure_utc(existing.check_in_time)
                        existing.total_hours = round(duration.total_seconds() / 3600, 2)
                    
                    existing.status = AttendanceStatus.CHECKED_OUT
                else:
                    # Calculate shift times for this attendance record
                    shift_start, shift_end, _ = get_shift_dates_and_times(
                        existing.attendance_date,
                        user_shift.shift_type.start_time,
                        user_shift.shift_type.end_time,
                        existing.check_in_time,
                        check_out_time
                    )
                    logger.info(f"Shift times for employee {employee.id} on {existing.attendance_date}: Start: {shift_start}, End: {shift_end}")
                    logger.info(f"Check-in time: {existing.check_in_time} Check-out time: {check_out_time}")

                    existing.check_out_time = check_out_time
                    existing.bio_check_out = data.bio_check_out or False
                    
                    # Calculate total hours
                    if existing.check_in_time:
                        duration = check_out_time - ensure_utc(existing.check_in_time)
                        existing.total_hours = round(duration.total_seconds() / 3600, 2)
                        
                        # Calculate early leave (only if not weekend/holiday)
                        if not existing.is_weekend and not existing.is_holiday:
                            if check_out_time < shift_end:
                                early = shift_end - check_out_time
                                existing.early_leave_minutes = int(early.total_seconds() / 60)
                            
                            # Calculate overtime (if checked out after shift end)
                            if check_out_time > shift_end:
                                overtime = check_out_time - shift_end
                                # Only count as overtime if it's significant (more than 15 minutes)
                                if overtime.total_seconds() > 900:  # 15 minutes
                                    existing.overtime_hours = round(overtime.total_seconds() / 3600, 2)
                    
                    # Set appropriate status
                    if existing.is_weekend:
                        existing.status = AttendanceStatus.WEEKEND
                    elif existing.is_holiday:
                        existing.status = AttendanceStatus.HOLIDAY
                    else:
                        # Determine final status based on check-in/out times
                        if existing.late_minutes > 0 and existing.early_leave_minutes > 0:
                            existing.status = AttendanceStatus.LEFT_EARLY  # Late and left early
                        elif existing.late_minutes > 0:
                            existing.status = AttendanceStatus.LATE
                        elif existing.early_leave_minutes > 0:
                            existing.status = AttendanceStatus.LEFT_EARLY
                        else:
                            existing.status = AttendanceStatus.PRESENT

                await self.session.commit()
                await self.session.refresh(existing, attribute_names=["employee", "created_at", "updated_at"])
                logger.info(f"Checked out: Employee {employee.id}, Shift Date: {existing.attendance_date}, Check-out: {check_out_time}")
                return AttendanceResponse.model_validate(existing, from_attributes=True)

            # ========== CHECK-IN LOGIC ==========
            # Check holiday and weekend status for the attendance date
            is_holiday = await self._check_holiday(data.attendance_date)
            is_weekend = await self._check_weekend_offday(data.employee_id, data.attendance_date)

            # Handle weekend/holiday auto-marking
            if (is_weekend or is_holiday) and not check_in_time and not check_out_time:
                status = AttendanceStatus.WEEKEND if is_weekend else AttendanceStatus.HOLIDAY
                attendance = Attendance(
                    employee_id=data.employee_id,
                    attendance_date=data.attendance_date,
                    status=status,
                    is_holiday=is_holiday,
                    is_weekend=is_weekend,
                    remarks=f"Auto-marked as {'weekend offday' if is_weekend else 'company holiday'}"
                )
                self.session.add(attendance)
                await self.session.commit()
                await self.session.refresh(attendance, attribute_names=["employee", "created_at", "updated_at"])
                logger.info(f"Auto-marked: Employee {employee.id} as {status}")
                return AttendanceResponse.model_validate(attendance, from_attributes=True)

            # Check for existing attendance record
            existing_res = await self.session.execute(
                select(Attendance).options(selectinload(Attendance.employee)).where(
                    Attendance.employee_id == data.employee_id,
                    Attendance.attendance_date == data.attendance_date
                )
            )
            existing = existing_res.scalars().first()

            if existing and existing.check_in_time:
                raise HTTPException(status_code=400, detail="Already checked in for this date")

            # Get shift information for calculations
            user_shift = await self._get_employee_shift(data.employee_id, data.attendance_date)
            
            # Initialize variables
            late_minutes = 0
            initial_status = AttendanceStatus.CHECKED_IN
            is_late = False
            
            # Calculate shift times and late minutes only if we have shift info and check-in time
            if user_shift and check_in_time and not is_weekend and not is_holiday:
                shift_start, shift_end, _ = get_shift_dates_and_times(
                    data.attendance_date,
                    user_shift.shift_type.start_time,
                    user_shift.shift_type.end_time,
                    check_in_time
                )
                
                # Calculate late minutes
                grace = timedelta(minutes=user_shift.shift_type.late_grace_minutes or 0)
                if check_in_time > (shift_start + grace):
                    diff = check_in_time - shift_start
                    late_minutes = int(diff.total_seconds() / 60)
                    initial_status = AttendanceStatus.LATE
                    is_late = True

            # Determine final initial status
            if is_weekend:
                initial_status = AttendanceStatus.WEEKEND
            elif is_holiday:
                initial_status = AttendanceStatus.HOLIDAY

            # Create or update attendance record
            if existing:
                # Update existing record
                existing.check_in_time = check_in_time
                existing.latitude = data.latitude
                existing.longitude = data.longitude
                existing.bio_check_in = data.bio_check_in or False
                existing.late_minutes = late_minutes
                existing.status = initial_status
                existing.remarks = data.remarks
                attendance = existing
            else:
                # Create new attendance record
                attendance = Attendance(
                    employee_id=data.employee_id,
                    attendance_date=data.attendance_date,
                    check_in_time=check_in_time,
                    latitude=data.latitude,
                    longitude=data.longitude,
                    bio_check_in=data.bio_check_in or False,
                    is_holiday=is_holiday,
                    is_weekend=is_weekend,
                    late_minutes=late_minutes,
                    status=initial_status,
                    remarks=data.remarks
                )
                self.session.add(attendance)

            await self.session.commit()
            await self.session.refresh(attendance, attribute_names=["employee", "created_at", "updated_at"])
            
            # Create late ticket if employee is late and has user_shift
            if is_late and user_shift and not is_weekend and not is_holiday:
                await self._create_late_ticket(data.employee_id, user_shift, data.attendance_date)
            
            logger.info(f"Checked in: Employee {employee.id} - Status: {initial_status}, Date: {data.attendance_date}, Late: {is_late}")
            return AttendanceResponse.model_validate(attendance, from_attributes=True)

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error marking attendance: {e}")
            raise HTTPException(status_code=500, detail="Error marking attendance")

    # ---------- Attendance Retrieval ----------
    async def get_attendance(
        self,
        page_index: int = 1,
        page_size: int = 100,
        employee_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[AttendanceStatus] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
            """Get paginated attendance records with filtering"""
            try:
                # Build base query with employee join
                query = (
                    select(Attendance)
                    .join(Employee, Attendance.employee_id == Employee.id)
                    .options(selectinload(Attendance.employee))
                    .where(Employee.is_active == True)
                )
                
                # Apply filters
                conditions = []
                
                if employee_id:
                    conditions.append(Attendance.employee_id == employee_id)
                
                if start_date:
                    conditions.append(Attendance.attendance_date >= start_date)
                
                if end_date:
                    conditions.append(Attendance.attendance_date <= end_date)
                
                if status:
                    conditions.append(Attendance.status == status)
                
                # Location manager restriction
                role_name = await self.user_service.get_specific_role_name_by_user(user_id, "location_manager")
                if role_name:
                    loc_res = await self.session.execute(
                        select(Location).where(Location.manager_id == user_id)
                    )
                    loc = loc_res.scalar_one_or_none()
                    if loc:
                        conditions.append(Employee.location_id == loc.id)
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                # Get total count
                count_query = (
                    select(func.count(Attendance.id))
                    .select_from(Attendance)
                    .join(Employee, Attendance.employee_id == Employee.id)
                    .where(Employee.is_active == True)
                )
                if conditions:
                    count_query = count_query.where(and_(*conditions))
                
                total_count = await self.session.scalar(count_query)
                
                # Calculate offset
                skip = (page_index - 1) * page_size
                
                # Get paginated data
                query = query.order_by(Attendance.attendance_date.desc())
                query = query.offset(skip).limit(page_size)
                
                result = await self.session.execute(query)
                attendances = result.scalars().all()
                
                return {
                    "page_index": page_index,
                    "page_size": page_size,
                    "count": total_count or 0,
                    "data": attendances
                }
                
            except Exception as e:
                logger.error(f"Error fetching attendance: {e}")
                return {
                    "page_index": page_index,
                    "page_size": page_size,
                    "count": 0,
                    "data": []
                }
    
    # ---------- Summary (Updated to handle weekends and night shifts) ----------
    async def get_employee_attendance_summary(self, employee_id: int, month: int, year: int) -> Dict:
        try:
            start = date(year, month, 1)
            end = (start.replace(month=month % 12 + 1, day=1) - timedelta(days=1)) if month < 12 else date(year, 12, 31)

            result = await self.session.execute(
                select(Attendance).where(
                    Attendance.employee_id == employee_id,
                    Attendance.attendance_date.between(start, end)
                )
            )
            records = result.scalars().all()

            total_days = (end - start).days + 1
            present = len([r for r in records if r.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.LEFT_EARLY, AttendanceStatus.CHECKED_OUT]])
            absent = len([r for r in records if r.status == AttendanceStatus.ABSENT])
            late = len([r for r in records if r.status == AttendanceStatus.LATE])
            weekend_days = len([r for r in records if r.status == AttendanceStatus.WEEKEND])
            holiday_days = len([r for r in records if r.status == AttendanceStatus.HOLIDAY])
            
            # Working days calculation (exclude weekends and holidays)
            working_days = total_days - weekend_days - holiday_days
            working_attendance = present  # Present days in working days
            
            total_hours = sum([r.total_hours or 0 for r in records if r.total_hours])
            overtime = sum([r.overtime_hours or 0 for r in records if r.overtime_hours])

            return {
                "employee_id": employee_id,
                "month": month,
                "year": year,
                "total_days": total_days,
                "working_days": working_days,
                "present_days": present,
                "absent_days": absent,
                "late_days": late,
                "weekend_days": weekend_days,
                "holiday_days": holiday_days,
                "total_working_hours": round(total_hours, 2),
                "total_overtime_hours": round(overtime, 2),
                "attendance_percentage": round((working_attendance / working_days) * 100, 2) if working_days > 0 else 0,
                "overall_attendance_percentage": round((present / total_days) * 100, 2)
            }

        except Exception as e:
            logger.error(f"Error summarizing attendance: {e}")
            return {}

    # ---------- AI Automation (Updated) ----------
    async def process_daily_attendance(self, process_date: date) -> Dict:
        try:
            logger.info(f"Processing attendance for {process_date}")

            emp_result = await self.session.execute(
                select(Employee).where(Employee.is_active == True)
            )
            employees = emp_result.scalars().all()

            absent_marked = 0
            weekend_marked = 0
            holiday_marked = 0

            # Check if it's a company holiday
            is_company_holiday = await self._check_holiday(process_date)

            for emp in employees:
                # Check if attendance already exists
                exist = await self.session.execute(
                    select(Attendance).where(
                        Attendance.employee_id == emp.id,
                        Attendance.attendance_date == process_date
                    )
                )
                if exist.scalar_one_or_none():
                    continue

                # Check if it's employee's weekend
                is_employee_weekend = await self._check_weekend_offday(emp.id, process_date)

                # Determine status and mark accordingly
                if is_company_holiday:
                    self.session.add(Attendance(
                        employee_id=emp.id,
                        attendance_date=process_date,
                        status=AttendanceStatus.HOLIDAY,
                        is_holiday=True,
                        is_weekend=False,
                        remarks="Auto-marked as company holiday"
                    ))
                    holiday_marked += 1
                elif is_employee_weekend:
                    self.session.add(Attendance(
                        employee_id=emp.id,
                        attendance_date=process_date,
                        status=AttendanceStatus.WEEKEND,
                        is_holiday=False,
                        is_weekend=True,
                        remarks="Auto-marked as weekend offday"
                    ))
                    weekend_marked += 1
                else:
                    # Check if this employee has a night shift that started previous day
                    # and is still ongoing (no check-out yet)
                    previous_date = process_date - timedelta(days=1)
                    night_shift_res = await self.session.execute(
                        select(Attendance).where(
                            Attendance.employee_id == emp.id,
                            Attendance.attendance_date == previous_date,
                            Attendance.check_in_time.isnot(None),
                            Attendance.check_out_time.is_(None)
                        )
                    )
                    ongoing_night_shift = night_shift_res.scalar_one_or_none()
                    
                    if ongoing_night_shift:
                        # Verify it's actually a night shift
                        user_shift = await self._get_employee_shift(emp.id, previous_date)
                        if user_shift and is_night_shift(user_shift.shift_type.start_time, user_shift.shift_type.end_time):
                            # Skip marking absent for today as employee is still on night shift from yesterday
                            logger.info(f"Skipping absent marking for employee {emp.id} - ongoing night shift from {previous_date}")
                            continue
                    
                    # Regular working day - mark as absent
                    self.session.add(Attendance(
                        employee_id=emp.id,
                        attendance_date=process_date,
                        status=AttendanceStatus.ABSENT,
                        is_holiday=False,
                        is_weekend=False,
                        remarks="Auto-marked as absent"
                    ))
                    absent_marked += 1
                    
                    # Create absent ticket after marking absent
                    await self.session.flush()  # Flush to ensure attendance is saved before creating ticket
                    await self._create_absent_ticket(emp.id, process_date)

            await self.session.commit()

            result = {
                "date": process_date.isoformat(),
                "total_employees": len(employees),
                "absent_marked": absent_marked,
                "weekend_marked": weekend_marked,
                "holiday_marked": holiday_marked,
                "message": "Daily attendance processed successfully"
            }
            logger.info(f"Processing complete: {result}")
            return result

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error processing daily attendance: {e}")
            raise HTTPException(status_code=500, detail="Attendance processing failed")