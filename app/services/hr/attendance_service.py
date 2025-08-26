import logging
from typing import Optional, List, Dict
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.models.hr.attendance import Attendance
from app.models.hr.employee import Employee
from app.models.hr.user_shift import UserShift
from app.models.hr.shift_type import ShiftType
from app.models.hr.holiday import Holiday
from app.models.shared.enums import AttendanceStatus
from app.schemas.hr.attendance_schema import AttendanceCreate, AttendanceResponse

logger = logging.getLogger(__name__)

def ensure_utc(dt: datetime | None) -> datetime | None:
        """Ensure datetime is timezone-aware (UTC)."""
        if dt is None:
            return None
        if dt.tzinfo is None:  # naive → assume UTC
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

class AttendanceService:
    def __init__(self, session: AsyncSession):
        self.session = session

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

            # Validate shift
            today = data.attendance_date
            shift_res = await self.session.execute(
                select(UserShift)
                .options(selectinload(UserShift.shift_type))
                .join(ShiftType)
                .where(
                    UserShift.employee_id == data.employee_id,
                    UserShift.is_active == True,
                    UserShift.effective_date <= today,
                    ((UserShift.end_date.is_(None)) | (UserShift.end_date >= today))
                )
            )
            user_shift = shift_res.scalars().first()
            if not user_shift:
                raise HTTPException(status_code=400, detail="No active shift for employee")

            # Normalize times
            check_in_time = ensure_utc(data.check_in_time)
            check_out_time = ensure_utc(data.check_out_time)

            # Shift start & end (UTC)
            shift_start = datetime.combine(data.attendance_date, user_shift.shift_type.start_time).replace(tzinfo=timezone.utc)
            shift_end = datetime.combine(data.attendance_date, user_shift.shift_type.end_time).replace(tzinfo=timezone.utc)

            # Check holiday
            holiday_res = await self.session.execute(
                select(Holiday).where(Holiday.date == data.attendance_date, Holiday.is_active == True)
            )
            is_holiday = holiday_res.scalars().first() is not None

            # Check existing attendance
            existing_res = await self.session.execute(
                select(Attendance).options(selectinload(Attendance.employee)).where(
                    Attendance.employee_id == data.employee_id,
                    Attendance.attendance_date == data.attendance_date
                )
            )
            existing = existing_res.scalars().first()

            # ========== CHECK-OUT ==========
            if existing:
                if check_out_time and not existing.check_out_time:
                    existing.check_out_time = check_out_time
                    existing.bio_check_out = data.bio_check_out or False

                    if existing.check_in_time:
                        duration = check_out_time - ensure_utc(existing.check_in_time)
                        existing.total_hours = round(duration.total_seconds() / 3600, 2)

                        if check_out_time < shift_end:
                            early = shift_end - check_out_time
                            existing.early_leave_minutes = int(early.total_seconds() / 60)

                    existing.status = AttendanceStatus.CHECKED_OUT
                    await self.session.commit()
                    await self.session.refresh(existing, attribute_names=["employee", "created_at", "updated_at"])
                    logger.info(f"Checked out: {employee.id}")
                    return AttendanceResponse.model_validate(existing, from_attributes=True)  # ✅ fix here
                else:
                    raise HTTPException(status_code=400, detail="Already checked in or invalid check-out")

            # ========== CHECK-IN ==========
            attendance = Attendance(
                employee_id=data.employee_id,
                attendance_date=data.attendance_date,
                check_in_time=check_in_time,
                latitude = data.latitude,
                longitude = data.longitude,
                bio_check_in=data.bio_check_in or False,
                is_holiday=is_holiday,
                status=AttendanceStatus.CHECKED_IN
            )

            if check_in_time:
                grace = timedelta(minutes=user_shift.shift_type.late_grace_minutes or 0)
                if check_in_time > (shift_start + grace):
                    diff = check_in_time - shift_start
                    attendance.late_minutes = int(diff.total_seconds() / 60)
                    attendance.status = AttendanceStatus.LATE

            self.session.add(attendance)
            await self.session.commit()
            await self.session.refresh(attendance, attribute_names=["employee", "created_at", "updated_at"])
            logger.info(f"Checked in: {employee.id}")
            return AttendanceResponse.model_validate(attendance, from_attributes=True)  # ✅ schema not ORM

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error marking attendance: {e}")
        raise HTTPException(status_code=500, detail="Error marking attendance")

    # ---------- Attendance Retrieval ----------
    async def get_attendance(
        self,
        employee_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[AttendanceStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Attendance]:
        try:
            query = select(Attendance).options(selectinload(Attendance.employee))
            if employee_id:
                query = query.where(Attendance.employee_id == employee_id)
            if start_date:
                query = query.where(Attendance.attendance_date >= start_date)
            if end_date:
                query = query.where(Attendance.attendance_date <= end_date)
            if status:
                query = query.where(Attendance.status == status)

            result = await self.session.execute(query.order_by(Attendance.attendance_date.desc()).offset(skip).limit(limit))
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error fetching attendance: {e}")
            return []

    # ---------- Summary ----------
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
            present = len([r for r in records if r.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.LEFT_EARLY]])
            absent = total_days - present
            late = len([r for r in records if r.status == AttendanceStatus.LATE])
            total_hours = sum([r.total_hours or 0 for r in records])
            overtime = sum([r.overtime_hours or 0 for r in records])

            return {
                "employee_id": employee_id,
                "month": month,
                "year": year,
                "total_days": total_days,
                "present_days": present,
                "absent_days": absent,
                "late_days": late,
                "total_working_hours": round(total_hours, 2),
                "total_overtime_hours": round(overtime, 2),
                "attendance_percentage": round((present / total_days) * 100, 2)
            }

        except Exception as e:
            logger.error(f"Error summarizing attendance: {e}")
            return {}

    # ---------- AI Automation ----------
    async def process_daily_attendance(self, process_date: date) -> Dict:
        try:
            logger.info(f"Processing attendance for {process_date}")

            emp_result = await self.session.execute(
                select(Employee).where(Employee.is_active == True)
            )
            employees = emp_result.scalars().all()

            absent_marked = 0

            for emp in employees:
                exist = await self.session.execute(
                    select(Attendance).where(
                        Attendance.employee_id == emp.id,
                        Attendance.attendance_date == process_date
                    )
                )
                if exist.scalar_one_or_none():
                    continue

                is_holiday = await self.session.execute(
                    select(Holiday).where(Holiday.date == process_date, Holiday.is_active == True)
                )
                if is_holiday.scalar_one_or_none():
                    continue

                self.session.add(Attendance(
                    employee_id=emp.id,
                    attendance_date=process_date,
                    status=AttendanceStatus.ABSENT,
                    is_holiday=False
                ))
                absent_marked += 1

            await self.session.commit()

            result = {
                "date": process_date.isoformat(),
                "total_employees": len(employees),
                "absent_marked": absent_marked,
                "message": "Daily attendance processed successfully"
            }
            logger.info(f"Processing complete: {result}")
            return result

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error processing daily attendance: {e}")
            raise HTTPException(status_code=500, detail="Attendance processing failed")