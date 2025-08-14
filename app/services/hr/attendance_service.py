from typing import List, Optional, Dict
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func, extract
from datetime import date, datetime, timedelta
from app.models.hr.attendance import Attendance
from app.models.hr.employee import Employee
from app.models.hr.user_shift import UserShift
from app.models.hr.shift_type import ShiftType
from app.models.hr.holiday import Holiday
from app.models.shared.enums import AttendanceStatus
from app.schemas.hr.attendance_schema import AttendanceCreate, AttendanceUpdate, AttendanceResponse
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import logger

class AttendanceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def mark_attendance(
        self,
        attendance_data: AttendanceCreate,
        current_user_id: int
    ) -> Attendance:
        """Mark employee attendance (check-in/check-out)"""
        try:
            # Validate employee
            employee = self.db.query(Employee).filter(
                Employee.id == attendance_data.employee_id,
                Employee.is_active == True
            ).first()
            if not employee:
                raise ValidationError(f"Employee with ID {attendance_data.employee_id} not found")

            # Get employee's current shift
            user_shift = self.db.query(UserShift).join(ShiftType).filter(
                UserShift.employee_id == attendance_data.employee_id,
                UserShift.is_active == True,
                UserShift.end_date.is_(None)
            ).first()

            if not user_shift:
                raise ValidationError(f"No active shift found for employee")

            # Check if attendance already exists for today
            existing_attendance = self.db.query(Attendance).filter(
                Attendance.employee_id == attendance_data.employee_id,
                Attendance.attendance_date == attendance_data.attendance_date
            ).first()

            # Check if it's a holiday
            is_holiday = self.db.query(Holiday).filter(
                Holiday.date == attendance_data.attendance_date,
                Holiday.is_active == True
            ).first() is not None

            if existing_attendance:
                # Update check-out
                if attendance_data.check_out_time and not existing_attendance.check_out_time:
                    existing_attendance.check_out_time = attendance_data.check_out_time
                    existing_attendance.bio_check_out = attendance_data.bio_check_out or False
                    
                    # Calculate total hours
                    if existing_attendance.check_in_time:
                        time_diff = attendance_data.check_out_time - existing_attendance.check_in_time
                        existing_attendance.total_hours = round(time_diff.total_seconds() / 3600, 2)
                        
                        # Calculate early leave
                        shift_end = datetime.combine(
                            attendance_data.attendance_date,
                            user_shift.shift_type.end_time
                        )
                        if attendance_data.check_out_time < shift_end:
                            early_diff = shift_end - attendance_data.check_out_time
                            existing_attendance.early_leave_minutes = int(early_diff.total_seconds() / 60)
                    
                    existing_attendance.status = AttendanceStatus.CHECKED_OUT
                    
                    self.db.commit()
                    self.db.refresh(existing_attendance)
                    
                    logger.info(f"Check-out recorded for employee {employee.employee_id}")
                    return existing_attendance
                else:
                    raise ValidationError("Attendance already marked for today or invalid check-out")

            else:
                # Create new attendance record (check-in)
                attendance = Attendance(
                    employee_id=attendance_data.employee_id,
                    attendance_date=attendance_data.attendance_date,
                    check_in_time=attendance_data.check_in_time,
                    bio_check_in=attendance_data.bio_check_in or False,
                    is_holiday=is_holiday,
                    status=AttendanceStatus.CHECKED_IN
                )

                # Calculate late minutes
                if attendance_data.check_in_time:
                    shift_start = datetime.combine(
                        attendance_data.attendance_date,
                        user_shift.shift_type.start_time
                    )
                    grace_period = timedelta(minutes=user_shift.shift_type.late_grace_minutes or 0)
                    
                    if attendance_data.check_in_time > (shift_start + grace_period):
                        late_diff = attendance_data.check_in_time - shift_start
                        attendance.late_minutes = int(late_diff.total_seconds() / 60)
                        attendance.status = AttendanceStatus.LATE

                self.db.add(attendance)
                self.db.commit()
                self.db.refresh(attendance)
                
                logger.info(f"Check-in recorded for employee {employee.employee_id}")
                return attendance
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error marking attendance: {str(e)}")
            raise

    async def get_attendance(
        self,
        employee_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[AttendanceStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Attendance]:
        """Get attendance records with filtering"""
        query = self.db.query(Attendance).options(
            joinedload(Attendance.employee)
        )

        if employee_id:
            query = query.filter(Attendance.employee_id == employee_id)

        if start_date:
            query = query.filter(Attendance.attendance_date >= start_date)

        if end_date:
            query = query.filter(Attendance.attendance_date <= end_date)

        if status:
            query = query.filter(Attendance.status == status)

        return query.order_by(Attendance.attendance_date.desc()).offset(skip).limit(limit).all()

    async def get_employee_attendance_summary(
        self,
        employee_id: int,
        month: int,
        year: int
    ) -> Dict:
        """Get employee attendance summary for a month"""
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        attendances = self.db.query(Attendance).filter(
            Attendance.employee_id == employee_id,
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date
        ).all()

        total_days = (end_date - start_date).days + 1
        present_days = len([a for a in attendances if a.status in [
            AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.LEFT_EARLY
        ]])
        absent_days = total_days - present_days
        late_days = len([a for a in attendances if a.status == AttendanceStatus.LATE])
        total_hours = sum([a.total_hours or 0 for a in attendances])
        total_overtime = sum([a.overtime_hours or 0 for a in attendances])

        return {
            "employee_id": employee_id,
            "month": month,
            "year": year,
            "total_days": total_days,
            "present_days": present_days,
            "absent_days": absent_days,
            "late_days": late_days,
            "total_working_hours": total_hours,
            "total_overtime_hours": total_overtime,
            "attendance_percentage": round((present_days / total_days) * 100, 2)
        }

    async def process_daily_attendance(self, process_date: date) -> Dict:
        """Process attendance for all employees for a specific date (AI automation)"""
        try:
            logger.info(f"Processing daily attendance for {process_date}")
            
            # Get all active employees
            employees = self.db.query(Employee).filter(Employee.is_active == True).all()
            
            processed = 0
            absent_marked = 0
            
            for employee in employees:
                # Check if attendance already exists
                existing = self.db.query(Attendance).filter(
                    Attendance.employee_id == employee.id,
                    Attendance.attendance_date == process_date
                ).first()
                
                if not existing:
                    # Check if it's a holiday
                    is_holiday = self.db.query(Holiday).filter(
                        Holiday.date == process_date,
                        Holiday.is_active == True
                    ).first() is not None
                    
                    if not is_holiday:
                        # Mark as absent
                        attendance = Attendance(
                            employee_id=employee.id,
                            attendance_date=process_date,
                            status=AttendanceStatus.ABSENT,
                            is_holiday=False
                        )
                        self.db.add(attendance)
                        absent_marked += 1
                
                processed += 1
            
            self.db.commit()
            
            result = {
                "date": process_date.isoformat(),
                "total_employees": processed,
                "absent_marked": absent_marked,
                "message": f"Daily attendance processed successfully"
            }
            
            logger.info(f"Daily attendance processing completed: {result}")
            return result
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing daily attendance: {str(e)}")
            raise