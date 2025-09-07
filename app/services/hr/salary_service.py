import logging
from typing import Any, Optional, List, Dict
from decimal import Decimal
from datetime import date, datetime, timedelta
from calendar import monthrange
from sqlalchemy import select, extract, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hr.salary import Salary
from app.models.hr.employee import Employee
from app.models.hr.attendance import Attendance
from app.models.shared.enums import SalaryPaymentStatus, AttendanceStatus
from app.schemas.hr.salary_schema import SalaryCreate
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class SalaryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_monthly_salary(self, employee_id: int, salary_month: date, current_user_id: int) -> Salary:
        today = date.today()
        if today.day < 25 and today.month == salary_month.month:
            raise HTTPException(status_code=400, detail="Salary can only be generated from 25th of the month")

        emp_res = await self.session.execute(
            select(Employee).where(Employee.id == employee_id, Employee.is_active == True)
        )
        employee = emp_res.scalar_one_or_none()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        salary_res = await self.session.execute(
            select(Salary).where(Salary.employee_id == employee_id, Salary.salary_month == salary_month)
        )
        if salary_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Salary already generated for this month")

        summary = await self._attendance_summary(employee_id, salary_month)
        overtime = await self._calculate_overtime(employee_id, salary_month)
        late_deduction = await self._calculate_late_deductions(employee_id, salary_month)
        absent_deduction = await self._calculate_absent_deductions(employee_id, salary_month, employee.basic_salary)

        gross = (employee.basic_salary or 0) + (employee.housing_allowance or 0) + (employee.transport_allowance or 0) + overtime
        deductions = late_deduction + absent_deduction
        net = gross - deductions

        salary = Salary(
            employee_id=employee_id,
            salary_month=salary_month,
            basic_salary=employee.basic_salary,
            housing_allowance=employee.housing_allowance,
            transport_allowance=employee.transport_allowance,
            overtime_amount=overtime,
            late_deductions=late_deduction,
            absent_deductions=absent_deduction,
            total_deductions=deductions,
            gross_salary=gross,
            net_salary=net,
            working_days=summary['working_days'],
            present_days=summary['present_days'],
            absent_days=summary['absent_days'],
            late_days=summary['late_days'],
            generated_by=current_user_id,
            payment_status=SalaryPaymentStatus.UNPAID
        )

        self.session.add(salary)
        await self.session.commit()
        await self.session.refresh(salary)
        logger.info(f"Salary generated for {employee.employee_id} on {salary_month}")
        return salary

    async def _attendance_summary(self, employee_id: int, salary_month: date) -> Dict:
        start, end = self._month_range(salary_month)
        res = await self.session.execute(
            select(Attendance).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date.between(start, end)
            )
        )
        records = res.scalars().all()
        return {
            "working_days": (end - start).days + 1,
            "present_days": len([r for r in records if r.status in [AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.LEFT_EARLY, AttendanceStatus.CHECKED_OUT]]),
            "absent_days": len([r for r in records if r.status == AttendanceStatus.ABSENT]),
            "late_days": len([r for r in records if r.status == AttendanceStatus.LATE])
        }

    async def _calculate_overtime(self, employee_id: int, salary_month: date) -> Decimal:
        start, end = self._month_range(salary_month)
        overtime_res = await self.session.execute(
            select(func.sum(Attendance.overtime_hours)).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date.between(start, end)
            )
        )
        total_ot = overtime_res.scalar() or 0

        emp_res = await self.session.execute(select(Employee).where(Employee.id == employee_id))
        emp = emp_res.scalar_one_or_none()

        if emp and emp.basic_salary:
            hourly = emp.basic_salary / Decimal('30') / Decimal('8')
            return Decimal(str(total_ot)) * hourly * Decimal('1.5')
        return Decimal('0')

    async def _calculate_late_deductions(self, employee_id: int, salary_month: date) -> Decimal:
        start, end = self._month_range(salary_month)
        count = await self.session.execute(
            select(func.count()).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date.between(start, end),
                Attendance.status == AttendanceStatus.LATE
            )
        )
        late_days = count.scalar() or 0
        return Decimal(late_days) * Decimal('50')

    async def _calculate_absent_deductions(self, employee_id: int, salary_month: date, basic_salary: Decimal) -> Decimal:
        start, end = self._month_range(salary_month)
        count = await self.session.execute(
            select(func.count()).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date.between(start, end),
                Attendance.status == AttendanceStatus.ABSENT,
                Attendance.is_holiday == False
            )
        )
        absent = count.scalar() or 0
        daily = basic_salary / Decimal(str((end - start).days + 1))
        return Decimal(absent) * daily

    async def generate_bulk_salary(self, salary_month: date, location_id: Optional[int], department_id: Optional[int], current_user_id: int) -> Dict:
        query = select(Employee).where(Employee.is_active == True)
        if location_id:
            query = query.where(Employee.location_id == location_id)
        if department_id:
            query = query.where(Employee.department_id == department_id)

        res = await self.session.execute(query)
        employees = res.scalars().all()
        stats = {"successful": 0, "failed": 0, "errors": []}

        for emp in employees:
            try:
                await self.generate_monthly_salary(emp.id, salary_month, current_user_id)
                stats["successful"] += 1
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"{emp.employee_id}: {str(e)}")

        stats.update({"total_employees": len(employees), "salary_month": salary_month.isoformat(), "errors": stats["errors"][:10]})
        logger.info(f"Bulk salary generated: {stats}")
        return stats

    async def mark_salary_paid(self, salary_id: int, payment_date: datetime, method: str, reference: str, user_id: int) -> Salary:
        res = await self.session.execute(select(Salary).where(Salary.id == salary_id))
        salary = res.scalar_one_or_none()
        if not salary:
            raise HTTPException(status_code=404, detail="Salary not found")
        if salary.payment_status == SalaryPaymentStatus.PAID:
            raise HTTPException(status_code=400, detail="Salary already paid")

        salary.payment_status = SalaryPaymentStatus.PAID
        salary.payment_date = payment_date
        salary.payment_method = method
        salary.payment_reference = reference

        await self.session.commit()
        await self.session.refresh(salary)
        logger.info(f"Salary marked paid: {salary_id} by {user_id}")
        return salary

    async def get_employee_salaries(
        self, 
        employee_id: int,
        page_index: int = 1,
        page_size: int = 12,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get paginated employee salary history"""
        try:
            conditions = [Salary.employee_id == employee_id]
            
            if year:
                conditions.append(extract('year', Salary.salary_month) == year)
            
            # Get total count
            total_count = await self.session.scalar(
                select(func.count(Salary.id)).where(*conditions)
            )
            
            # Calculate offset
            skip = (page_index - 1) * page_size
            
            # Get paginated data
            salaries = await self.session.scalars(
                select(Salary)
                .where(*conditions)
                .order_by(Salary.salary_month.desc())
                .offset(skip)
                .limit(page_size)
            )
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": salaries.all()
            }
            
        except Exception as e:
            logger.error(f"Error getting employee salaries: {e}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def get_salary_reports(self, month: int, year: int, location_id: Optional[int], department_id: Optional[int]) -> Dict:
        salary_date = date(year, month, 1)
        query = (
            select(Salary)
            .join(Employee)
            .where(
                extract("month", Salary.salary_month) == month,
                extract("year", Salary.salary_month) == year,
                Employee.is_active == True
            )
        )
        if location_id:
            query = query.where(Employee.location_id == location_id)
        if department_id:
            query = query.where(Employee.department_id == department_id)

        res = await self.session.execute(query)
        salaries = res.scalars().all()

        total = len(salaries)
        gross = sum(s.gross_salary for s in salaries)
        net = sum(s.net_salary for s in salaries)
        deductions = sum(s.total_deductions for s in salaries)
        paid = len([s for s in salaries if s.payment_status == SalaryPaymentStatus.PAID])

        return {
            "month": month,
            "year": year,
            "total_employees": total,
            "total_gross_salary": float(gross),
            "total_net_salary": float(net),
            "total_deductions": float(deductions),
            "paid_salaries": paid,
            "unpaid_salaries": total - paid,
            "average_salary": float(net / total) if total else 0
        }

    def _month_range(self, month_date: date) -> tuple:
        last_day = monthrange(month_date.year, month_date.month)[1]
        return month_date.replace(day=1), month_date.replace(day=last_day)
