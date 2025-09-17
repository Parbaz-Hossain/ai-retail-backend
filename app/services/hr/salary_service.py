import logging
from typing import Any, Optional, List, Dict
from decimal import Decimal
from datetime import date, datetime, timedelta
from calendar import monthrange
from sqlalchemy import delete, select, extract, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hr.deduction import SalaryDeduction
from app.models.hr.salary import Salary
from app.models.hr.employee import Employee
from app.models.hr.attendance import Attendance
from app.models.shared.enums import SalaryPaymentStatus, AttendanceStatus
from app.schemas.hr.salary_schema import SalaryCreate
from app.services.hr.deduction_service import DeductionService
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class SalaryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.deduction_service = DeductionService(session)

    async def generate_monthly_salary(self, employee_id: int, salary_month: date, current_user_id: int) -> Salary:
        """Generate monthly salary with integrated deduction calculation"""
        today = date.today()
        if today.day < 25 and today.month == salary_month.month:
            raise HTTPException(status_code=400, detail="Salary can only be generated from 25th of the month")

        # Get employee
        emp_res = await self.session.execute(
            select(Employee).where(Employee.id == employee_id, Employee.is_active == True)
        )
        employee = emp_res.scalar_one_or_none()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Check if salary already generated
        salary_res = await self.session.execute(
            select(Salary).where(Salary.employee_id == employee_id, Salary.salary_month == salary_month)
        )
        if salary_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Salary already generated for this month")

        # Calculate attendance summary
        summary = await self._attendance_summary(employee_id, salary_month)
        
        # Calculate overtime
        overtime = await self._calculate_overtime(employee_id, salary_month)
        
        # Calculate gross salary
        gross = (employee.basic_salary or 0) + (employee.housing_allowance or 0) + (employee.transport_allowance or 0) + overtime
        
        # Calculate deductions using new deduction service
        total_deductions, deduction_details = await self.deduction_service.calculate_monthly_deductions(
            employee_id, salary_month
        )
        
        # Extract individual deduction amounts for backward compatibility
        late_deductions = sum(d['amount'] for d in deduction_details if d.get('type_name', '').lower() == 'late')
        absent_deductions = sum(d['amount'] for d in deduction_details if d.get('type_name', '').lower() == 'absent')
        other_deductions = sum(d['amount'] for d in deduction_details if d.get('type_name', '').lower() not in ['late', 'absent'])
        
        # Calculate net salary
        net = gross - total_deductions

        # Create salary record
        salary = Salary(
            employee_id=employee_id,
            salary_month=salary_month,
            basic_salary=employee.basic_salary,
            housing_allowance=employee.housing_allowance,
            transport_allowance=employee.transport_allowance,
            overtime_amount=overtime,
            late_deductions=late_deductions,
            absent_deductions=absent_deductions,
            other_deductions=other_deductions,
            total_deductions=total_deductions,
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
        
        # Apply deductions to salary and update employee deduction records
        await self.deduction_service.apply_deductions_to_salary(
            salary.id, employee_id, salary_month, deduction_details
        )
        
        logger.info(f"Salary generated for {employee.employee_id} on {salary_month} with total deductions: {total_deductions}")
        return salary

    async def _attendance_summary(self, employee_id: int, salary_month: date) -> Dict:
        """Calculate attendance summary for the month"""
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
        """Calculate overtime amount for the month"""
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

    async def generate_bulk_salary(self, salary_month: date, location_id: Optional[int], department_id: Optional[int], current_user_id: int) -> Dict:
        """Generate salary for multiple employees with integrated deduction calculation"""
        query = select(Employee).where(Employee.is_active == True)
        if location_id:
            query = query.where(Employee.location_id == location_id)
        if department_id:
            query = query.where(Employee.department_id == department_id)

        res = await self.session.execute(query)
        employees = res.scalars().all()
        stats = {"successful": 0, "failed": 0, "errors": [], "total_deductions": 0}

        for emp in employees:
            try:
                salary = await self.generate_monthly_salary(emp.id, salary_month, current_user_id)
                stats["successful"] += 1
                stats["total_deductions"] += float(salary.total_deductions)
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"{emp.employee_id}: {str(e)}")

        stats.update({
            "total_employees": len(employees), 
            "salary_month": salary_month.isoformat(), 
            "errors": stats["errors"][:10]
        })
        logger.info(f"Bulk salary generated: {stats}")
        return stats

    async def mark_salary_paid(self, salary_id: int, payment_date: datetime, method: str, reference: str, user_id: int) -> Salary:
        """Mark salary as paid"""
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
        """Get paginated employee salary history with deduction details"""
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
            
            # Get paginated data with deduction details
            salaries = await self.session.scalars(
                select(Salary)
                .options(selectinload(Salary.deduction_details))
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
        """Get salary reports with deduction breakdown"""
        salary_date = date(year, month, 1)
        query = (
            select(Salary)
            .join(Employee)
            .options(selectinload(Salary.deduction_details))
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
        
        # Calculate deduction breakdown
        deduction_breakdown = {}
        for salary in salaries:
            for deduction_detail in salary.deduction_details:
                type_name = deduction_detail.deduction_type.name if deduction_detail.deduction_type else "Unknown"
                if type_name not in deduction_breakdown:
                    deduction_breakdown[type_name] = 0
                deduction_breakdown[type_name] += float(deduction_detail.deducted_amount)

        return {
            "month": month,
            "year": year,
            "total_employees": total,
            "total_gross_salary": float(gross),
            "total_net_salary": float(net),
            "total_deductions": float(deductions),
            "deduction_breakdown": deduction_breakdown,
            "paid_salaries": paid,
            "unpaid_salaries": total - paid,
            "average_salary": float(net / total) if total else 0
        }

    def _month_range(self, month_date: date) -> tuple:
        """Get first and last day of the month"""
        last_day = monthrange(month_date.year, month_date.month)[1]
        return month_date.replace(day=1), month_date.replace(day=last_day)

    # New methods for deduction management
    async def get_salary_with_deduction_details(self, salary_id: int) -> Optional[Salary]:
        """Get salary with complete deduction details"""
        result = await self.session.execute(
            select(Salary)
            .options(
                selectinload(Salary.deduction_details).selectinload(SalaryDeduction.deduction_type),
                selectinload(Salary.deduction_details).selectinload(SalaryDeduction.employee_deduction)
            )
            .where(Salary.id == salary_id)
        )
        return result.scalar_one_or_none()

    async def recalculate_salary_deductions(self, salary_id: int, current_user_id: int) -> Salary:
        """Recalculate deductions for an existing salary"""
        salary = await self.session.get(Salary, salary_id)
        if not salary:
            raise HTTPException(status_code=404, detail="Salary not found")
        
        if salary.payment_status == SalaryPaymentStatus.PAID:
            raise HTTPException(status_code=400, detail="Cannot recalculate paid salary")
        
        # Delete existing deduction details
        await self.session.execute(
            delete(SalaryDeduction).where(SalaryDeduction.salary_id == salary_id)
        )
        
        # Recalculate deductions
        total_deductions, deduction_details = await self.deduction_service.calculate_monthly_deductions(
            salary.employee_id, salary.salary_month
        )
        
        # Update salary deduction amounts
        late_deductions = sum(d['amount'] for d in deduction_details if d.get('type_name', '').lower() == 'late')
        absent_deductions = sum(d['amount'] for d in deduction_details if d.get('type_name', '').lower() == 'absent')
        other_deductions = sum(d['amount'] for d in deduction_details if d.get('type_name', '').lower() not in ['late', 'absent'])
        
        salary.late_deductions = late_deductions
        salary.absent_deductions = absent_deductions
        salary.other_deductions = other_deductions
        salary.total_deductions = total_deductions
        salary.net_salary = salary.gross_salary - total_deductions
        
        await self.session.commit()
        
        # Apply new deductions
        await self.deduction_service.apply_deductions_to_salary(
            salary.id, salary.employee_id, salary.salary_month, deduction_details
        )
        
        await self.session.refresh(salary)
        logger.info(f"Salary deductions recalculated for salary {salary_id} by user {current_user_id}")
        return salary