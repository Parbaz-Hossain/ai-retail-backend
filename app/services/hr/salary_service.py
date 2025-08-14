from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, extract, func
from datetime import date, datetime, timedelta
from decimal import Decimal
from app.models.hr.salary import Salary
from app.models.hr.employee import Employee
from app.models.hr.attendance import Attendance
from app.models.shared.enums import SalaryPaymentStatus, AttendanceStatus
from app.schemas.hr.salary_schema import SalaryCreate, SalaryUpdate, SalaryResponse
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import logger
from calendar import monthrange

class SalaryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_monthly_salary(
        self,
        employee_id: int,
        salary_month: date,
        current_user_id: int
    ) -> Salary:
        """Generate salary for an employee for a specific month"""
        try:
            # Validate that salary generation is allowed (from 25th day onwards)
            today = date.today()
            if today.day < 25 and today.month == salary_month.month:
                raise ValidationError("Salary can only be generated from 25th day of the month")

            # Validate employee
            employee = self.db.query(Employee).filter(
                Employee.id == employee_id,
                Employee.is_active == True
            ).first()
            if not employee:
                raise ValidationError(f"Employee with ID {employee_id} not found")

            # Check if salary already generated for this month
            existing_salary = self.db.query(Salary).filter(
                Salary.employee_id == employee_id,
                Salary.salary_month == salary_month
            ).first()
            if existing_salary:
                raise ValidationError(f"Salary already generated for {salary_month.strftime('%B %Y')}")

            # Get attendance summary for the month
            attendance_summary = await self._calculate_attendance_summary(employee_id, salary_month)
            
            # Calculate salary components
            basic_salary = employee.basic_salary or Decimal('0')
            housing_allowance = employee.housing_allowance or Decimal('0')
            transport_allowance = employee.transport_allowance or Decimal('0')
            
            # Calculate overtime
            overtime_amount = await self._calculate_overtime_amount(employee_id, salary_month)
            
            # Calculate deductions
            late_deductions = await self._calculate_late_deductions(employee_id, salary_month)
            absent_deductions = await self._calculate_absent_deductions(employee_id, salary_month, basic_salary)
            
            # Calculate gross and net salary
            gross_salary = basic_salary + housing_allowance + transport_allowance + overtime_amount
            total_deductions = late_deductions + absent_deductions
            net_salary = gross_salary - total_deductions

            salary = Salary(
                employee_id=employee_id,
                salary_month=salary_month,
                basic_salary=basic_salary,
                housing_allowance=housing_allowance,
                transport_allowance=transport_allowance,
                overtime_amount=overtime_amount,
                late_deductions=late_deductions,
                absent_deductions=absent_deductions,
                total_deductions=total_deductions,
                gross_salary=gross_salary,
                net_salary=net_salary,
                working_days=attendance_summary['working_days'],
                present_days=attendance_summary['present_days'],
                absent_days=attendance_summary['absent_days'],
                late_days=attendance_summary['late_days'],
                generated_by=current_user_id,
                payment_status=SalaryPaymentStatus.UNPAID
            )

            self.db.add(salary)
            self.db.commit()
            self.db.refresh(salary)

            logger.info(f"Salary generated for employee {employee.employee_id} for {salary_month.strftime('%B %Y')}")
            return salary

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error generating salary: {str(e)}")
            raise

    async def _calculate_attendance_summary(self, employee_id: int, salary_month: date) -> Dict:
        """Calculate attendance summary for salary calculation"""
        _, last_day = monthrange(salary_month.year, salary_month.month)
        start_date = salary_month.replace(day=1)
        end_date = salary_month.replace(day=last_day)

        attendances = self.db.query(Attendance).filter(
            Attendance.employee_id == employee_id,
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date
        ).all()

        working_days = last_day
        present_days = len([a for a in attendances if a.status in [
            AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.LEFT_EARLY, AttendanceStatus.CHECKED_OUT
        ]])
        absent_days = len([a for a in attendances if a.status == AttendanceStatus.ABSENT])
        late_days = len([a for a in attendances if a.status == AttendanceStatus.LATE])

        return {
            'working_days': working_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'late_days': late_days
        }

    async def _calculate_overtime_amount(self, employee_id: int, salary_month: date) -> Decimal:
        """Calculate overtime amount"""
        _, last_day = monthrange(salary_month.year, salary_month.month)
        start_date = salary_month.replace(day=1)
        end_date = salary_month.replace(day=last_day)

        total_overtime = self.db.query(func.sum(Attendance.overtime_hours)).filter(
            Attendance.employee_id == employee_id,
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date
        ).scalar() or 0

        # Assuming overtime rate is 1.5x hourly rate
        employee = self.db.query(Employee).filter(Employee.id == employee_id).first()
        if employee and employee.basic_salary:
            hourly_rate = employee.basic_salary / Decimal('30') / Decimal('8')  # Assuming 30 days, 8 hours per day
            overtime_rate = hourly_rate * Decimal('1.5')
            return Decimal(str(total_overtime)) * overtime_rate
        
        return Decimal('0')

    async def _calculate_late_deductions(self, employee_id: int, salary_month: date) -> Decimal:
        """Calculate late deductions"""
        # Implementation depends on company policy
        # For now, assuming fixed deduction per late day
        _, last_day = monthrange(salary_month.year, salary_month.month)
        start_date = salary_month.replace(day=1)
        end_date = salary_month.replace(day=last_day)

        late_days = self.db.query(Attendance).filter(
            Attendance.employee_id == employee_id,
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date,
            Attendance.status == AttendanceStatus.LATE
        ).count()

        # Assuming 50 BDT deduction per late day
        return Decimal(str(late_days)) * Decimal('50')

    async def _calculate_absent_deductions(self, employee_id: int, salary_month: date, basic_salary: Decimal) -> Decimal:
        """Calculate absent deductions"""
        _, last_day = monthrange(salary_month.year, salary_month.month)
        start_date = salary_month.replace(day=1)
        end_date = salary_month.replace(day=last_day)

        absent_days = self.db.query(Attendance).filter(
            Attendance.employee_id == employee_id,
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date,
            Attendance.status == AttendanceStatus.ABSENT,
            Attendance.is_holiday == False
        ).count()

        # Daily salary deduction for absent days
        daily_salary = basic_salary / Decimal(str(last_day))
        return Decimal(str(absent_days)) * daily_salary

    async def generate_bulk_salary(
        self,
        salary_month: date,
        location_id: Optional[int] = None,
        department_id: Optional[int] = None,
        current_user_id: int = None
    ) -> Dict:
        """Generate salary for multiple employees (AI automation)"""
        try:
            query = self.db.query(Employee).filter(Employee.is_active == True)
            
            if location_id:
                query = query.filter(Employee.location_id == location_id)
            if department_id:
                query = query.filter(Employee.department_id == department_id)

            employees = query.all()
            
            successful = 0
            failed = 0
            errors = []

            for employee in employees:
                try:
                    await self.generate_monthly_salary(employee.id, salary_month, current_user_id)
                    successful += 1
                except Exception as e:
                    failed += 1
                    errors.append(f"Employee {employee.employee_id}: {str(e)}")

            result = {
                "salary_month": salary_month.isoformat(),
                "total_employees": len(employees),
                "successful": successful,
                "failed": failed,
                "errors": errors[:10]  # Limit errors to first 10
            }

            logger.info(f"Bulk salary generation completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Error in bulk salary generation: {str(e)}")
            raise

    async def mark_salary_paid(
        self,
        salary_id: int,
        payment_date: datetime,
        payment_method: str,
        payment_reference: str,
        current_user_id: int
    ) -> Salary:
        """Mark salary as paid"""
        salary = self.db.query(Salary).filter(Salary.id == salary_id).first()
        if not salary:
            raise NotFoundError(f"Salary record with ID {salary_id} not found")

        if salary.payment_status == SalaryPaymentStatus.PAID:
            raise ValidationError("Salary is already marked as paid")

        salary.payment_status = SalaryPaymentStatus.PAID
        salary.payment_date = payment_date
        salary.payment_method = payment_method
        salary.payment_reference = payment_reference

        self.db.commit()
        self.db.refresh(salary)

        logger.info(f"Salary marked as paid: ID {salary_id} by user {current_user_id}")
        return salary

    async def get_employee_salaries(
        self,
        employee_id: int,
        year: Optional[int] = None,
        skip: int = 0,
        limit: int = 12
    ) -> List[Salary]:
        """Get employee salary history"""
        query = self.db.query(Salary).filter(Salary.employee_id == employee_id)
        
        if year:
            query = query.filter(extract('year', Salary.salary_month) == year)
        
        return query.order_by(Salary.salary_month.desc()).offset(skip).limit(limit).all()

    async def get_salary_reports(
        self,
        month: int,
        year: int,
        location_id: Optional[int] = None,
        department_id: Optional[int] = None
    ) -> Dict:
        """Get salary reports for management"""
        salary_date = date(year, month, 1)
        
        query = self.db.query(Salary).join(Employee).filter(
            Salary.salary_month == salary_date,
            Employee.is_active == True
        )
        
        if location_id:
            query = query.filter(Employee.location_id == location_id)
        if department_id:
            query = query.filter(Employee.department_id == department_id)
        
        salaries = query.all()
        
        total_employees = len(salaries)
        total_gross_salary = sum([s.gross_salary for s in salaries])
        total_net_salary = sum([s.net_salary for s in salaries])
        total_deductions = sum([s.total_deductions for s in salaries])
        paid_salaries = len([s for s in salaries if s.payment_status == SalaryPaymentStatus.PAID])
        unpaid_salaries = total_employees - paid_salaries

        return {
            "month": month,
            "year": year,
            "total_employees": total_employees,
            "total_gross_salary": float(total_gross_salary),
            "total_net_salary": float(total_net_salary),
            "total_deductions": float(total_deductions),
            "paid_salaries": paid_salaries,
            "unpaid_salaries": unpaid_salaries,
            "average_salary": float(total_net_salary / total_employees) if total_employees > 0 else 0
        }