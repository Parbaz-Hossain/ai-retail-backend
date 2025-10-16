import logging
from typing import Any, Optional, List, Dict
from decimal import Decimal
from datetime import date, datetime, timedelta
from calendar import monthrange
from sqlalchemy import delete, select, extract, func, and_
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
        # if today.day < 25 and today.month == salary_month.month:
        #     raise HTTPException(status_code=400, detail="Salary can only be generated from 25th of the month")

        # Get employee
        emp_res = await self.session.execute(
            select(Employee).where(Employee.id == employee_id, Employee.is_active == True)
        )
        employee = emp_res.scalar_one_or_none()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Check if salary already generated for this month (improved check)
        salary_res = await self.session.execute(
            select(Salary).where(
                Salary.employee_id == employee_id,
                extract('year', Salary.salary_month) == salary_month.year,
                extract('month', Salary.salary_month) == salary_month.month
            )
        )
        if salary_res.scalar_one_or_none():
            raise HTTPException(
                status_code=400, 
                detail=f"Salary already generated for {salary_month.strftime('%B %Y')}"
            )

        # Calculate attendance summary with proper working days calculation
        summary = await self._attendance_summary(employee_id, salary_month)
        
        # Calculate per-day salary rates
        monthly_basic = employee.basic_salary or Decimal('0')
        monthly_housing = employee.housing_allowance or Decimal('0')
        monthly_transport = employee.transport_allowance or Decimal('0')
        logger.info(f"Monthly Salary Components for {employee.employee_id}: Basic={monthly_basic}, Housing={monthly_housing}, Transport={monthly_transport}")
        
        # Calculate daily rates based on working days
        working_days = summary['working_days']
        if working_days > 0:
            daily_basic = monthly_basic / Decimal(str(working_days))
            daily_housing = monthly_housing / Decimal(str(working_days))
            daily_transport = monthly_transport / Decimal(str(working_days))
        else:
            daily_basic = daily_housing = daily_transport = Decimal('0')
        
        # Calculate prorated salary based on actual present days
        present_days = summary['present_days']
        prorated_basic = daily_basic * Decimal(str(present_days))
        prorated_housing = daily_housing * Decimal(str(present_days))
        prorated_transport = daily_transport * Decimal(str(present_days))
        
        # Calculate overtime
        overtime = await self._calculate_overtime(employee_id, salary_month)
        
        # Calculate gross salary (prorated base + overtime)
        gross = prorated_basic + prorated_housing + prorated_transport + overtime
        
        # Calculate deductions using updated deduction service (handles carryover automatically)
        total_deductions, deduction_details = await self.deduction_service.calculate_monthly_deductions(
            employee_id, salary_month
        )
        
        # Extract individual deduction amounts for backward compatibility
        late_deductions = sum(d['amount'] for d in deduction_details if d.get('type_name', '').lower() == 'late')
        absent_deductions = sum(d['amount'] for d in deduction_details if d.get('type_name', '').lower() == 'absent')
        other_deductions = sum(d['amount'] for d in deduction_details if d.get('type_name', '').lower() not in ['late', 'absent'])
        
        # Calculate net salary
        net = gross - total_deductions

        # Create salary record with prorated amounts
        salary = Salary(
            employee_id=employee_id,
            salary_month=salary_month,
            basic_salary=monthly_basic,
            housing_allowance=monthly_housing,
            transport_allowance=monthly_transport,
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
        
        logger.info(
            f"Salary generated for {employee.employee_id} on {salary_month} | "
            f"Working Days: {working_days} | Present: {present_days} | "
            f"Gross: {gross} | Deductions: {total_deductions} | Net: {net}"
        )
        return salary
    
    async def _attendance_summary(self, employee_id: int, salary_month: date) -> Dict:
        """
        Calculate attendance summary with proper working days calculation.
        Working days = Total days - Weekends - Holidays
        Present days = Actual days worked (PRESENT, LATE, LEFT_EARLY, CHECKED_OUT statuses)
        """
        start, end = self._month_range(salary_month)
        
        # Get all attendance records for the month
        res = await self.session.execute(
            select(Attendance).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date.between(start, end)
            )
        )
        records = res.scalars().all()
        
        # Calculate total calendar days
        total_days = (end - start).days + 1
        
        # Count weekends and holidays
        weekend_days = len([r for r in records if r.status == AttendanceStatus.WEEKEND or r.is_weekend])
        holiday_days = len([r for r in records if r.status == AttendanceStatus.HOLIDAY or r.is_holiday])
        
        # Working days = Total days - Weekends - Holidays
        working_days = total_days - weekend_days - holiday_days
        
        # Present days = Days actually worked (excluding weekends/holidays/absents)
        present_days = len([
            r for r in records 
            if r.status in [
                AttendanceStatus.PRESENT, 
                AttendanceStatus.LATE, 
                AttendanceStatus.LEFT_EARLY, 
                AttendanceStatus.CHECKED_OUT
            ]
        ])
        
        # Absent days (excluding weekends and holidays)
        absent_days = len([
            r for r in records 
            if r.status == AttendanceStatus.ABSENT and not r.is_weekend and not r.is_holiday
        ])
        
        # Late days
        late_days = len([r for r in records if r.status == AttendanceStatus.LATE])
        
        # Validation: present + absent should not exceed working days
        # If there are unrecorded days, they're considered absent
        unrecorded_absent = max(0, working_days - present_days - absent_days)
        total_absent = absent_days + unrecorded_absent
        
        return {
            "total_days": total_days,
            "working_days": working_days,
            "weekend_days": weekend_days,
            "holiday_days": holiday_days,
            "present_days": present_days,
            "absent_days": total_absent,
            "late_days": late_days
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

        if emp and emp.basic_salary and total_ot > 0:
            # Calculate hourly rate based on basic salary
            # Assuming 30 days/month and 8 hours/day
            hourly_rate = emp.basic_salary / Decimal('30') / Decimal('8')
            # Overtime is typically 1.5x hourly rate
            return Decimal(str(total_ot)) * hourly_rate * Decimal('1.5')
        
        return Decimal('0')

    async def generate_bulk_salary(
        self, 
        salary_month: date, 
        location_id: Optional[int], 
        department_id: Optional[int], 
        current_user_id: int
    ) -> Dict:
        """Generate salary for multiple employees with integrated deduction calculation"""
        query = select(Employee).where(Employee.is_active == True)
        
        if location_id:
            query = query.where(Employee.location_id == location_id)
        if department_id:
            query = query.where(Employee.department_id == department_id)

        res = await self.session.execute(query)
        employees = res.scalars().all()
        
        stats = {
            "successful": 0, 
            "failed": 0, 
            "skipped": 0,
            "errors": [], 
            "total_deductions": 0,
            "total_gross": 0,
            "total_net": 0
        }

        for emp in employees:
            try:
                # Check if salary already exists for this employee in this month
                existing_salary_res = await self.session.execute(
                    select(Salary).where(
                        Salary.employee_id == emp.id,
                        extract('year', Salary.salary_month) == salary_month.year,
                        extract('month', Salary.salary_month) == salary_month.month
                    )
                )
                
                if existing_salary_res.scalar_one_or_none():
                    stats["skipped"] += 1
                    logger.info(f"Skipped {emp.employee_id} - salary already exists for {salary_month.strftime('%B %Y')}")
                    continue
                
                # Generate salary
                salary = await self.generate_monthly_salary(emp.id, salary_month, current_user_id)
                stats["successful"] += 1
                stats["total_deductions"] += float(salary.total_deductions)
                stats["total_gross"] += float(salary.gross_salary)
                stats["total_net"] += float(salary.net_salary)
                
            except HTTPException as he:
                stats["failed"] += 1
                stats["errors"].append(f"{emp.employee_id}: {he.detail}")
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"{emp.employee_id}: {str(e)}")

        stats.update({
            "total_employees": len(employees),
            "salary_month": salary_month.isoformat(),
            "errors": stats["errors"][:10]  # Limit errors shown
        })
        
        logger.info(
            f"Bulk salary generated for {salary_month.strftime('%B %Y')} | "
            f"Success: {stats['successful']} | Failed: {stats['failed']} | Skipped: {stats['skipped']}"
        )
        return stats

    async def mark_salary_paid(
        self, 
        salary_id: int, 
        payment_date: datetime, 
        method: str, 
        reference: str, 
        user_id: int
    ) -> Salary:
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

    async def get_salary_reports(
        self, 
        month: int, 
        year: int, 
        location_id: Optional[int], 
        department_id: Optional[int]
    ) -> Dict:
        """Get salary reports with deduction breakdown"""
        salary_date = date(year, month, 1)
        query = (
            select(Salary)
            .join(Employee)
            .options(
                selectinload(Salary.deduction_details).selectinload(SalaryDeduction.deduction_type)
            )
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

    async def get_all_salaries(
        self,
        page_index: int = 1,
        page_size: int = 20,
        month: Optional[int] = None,
        year: Optional[int] = None,
        location_id: Optional[int] = None,
        department_id: Optional[int] = None,
        payment_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get paginated list of all employee salaries with filters
        """
        try:
            # Build base query with employee join
            query = (
                select(Salary)
                .join(Employee, Salary.employee_id == Employee.id)
                .options(selectinload(Salary.employee))
                .where(Employee.is_active == True)
            )
            
            # Apply filters
            conditions = []
            
            if month:
                conditions.append(extract('month', Salary.salary_month) == month)
            
            if year:
                conditions.append(extract('year', Salary.salary_month) == year)
            
            if location_id:
                conditions.append(Employee.location_id == location_id)
            
            if department_id:
                conditions.append(Employee.department_id == department_id)
            
            if payment_status:
                try:
                    status_enum = SalaryPaymentStatus[payment_status.upper()]
                    conditions.append(Salary.payment_status == status_enum)
                except KeyError:
                    pass  # Invalid status, ignore filter
            
            if conditions:
                query = query.where(and_(*conditions))
            
            # Get total count
            count_query = select(func.count(Salary.id)).select_from(Salary).join(Employee)
            if conditions:
                count_query = count_query.where(and_(*conditions))
            
            total_count = await self.session.scalar(count_query)
            
            # Calculate offset
            skip = (page_index - 1) * page_size
            
            # Get paginated data
            query = query.order_by(Salary.salary_month.desc(), Salary.created_at.desc())
            query = query.offset(skip).limit(page_size)
            
            result = await self.session.execute(query)
            salaries = result.scalars().all()
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": salaries
            }
            
        except Exception as e:
            logger.error(f"Error getting all salaries: {e}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
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