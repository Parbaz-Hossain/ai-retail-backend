import logging
from typing import Any, Optional, List, Dict, Tuple
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hr.deduction import DeductionType, EmployeeDeduction, SalaryDeduction
from app.models.hr.employee import Employee
from app.models.hr.attendance import Attendance
from app.models.shared.enums import DeductionStatus, DeductionTypeEnum, AttendanceStatus
from app.schemas.hr.deduction_schema import (
    DeductionTypeCreate, DeductionTypeUpdate,
    EmployeeDeductionCreate, EmployeeDeductionUpdate,
    BulkDeductionCreate
)
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class DeductionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ======================================= Deduction Type CRUD ============================================ #
    async def create_deduction_type(self, data: DeductionTypeCreate) -> DeductionType:
        # Check if deduction type already exists
        existing = await self.session.scalar(
            select(DeductionType).where(DeductionType.name == data.name)
        )
        if existing:
            raise HTTPException(status_code=400, detail="Deduction type already exists")
        
        deduction_type = DeductionType(**data.dict())
        self.session.add(deduction_type)
        await self.session.commit()
        await self.session.refresh(deduction_type)
        return deduction_type

    async def get_deduction_types(self, active_only: bool = True) -> List[DeductionType]:
        query = select(DeductionType)
        if active_only:
            query = query.where(DeductionType.is_active == True)
        
        result = await self.session.execute(query.order_by(DeductionType.name))
        return result.scalars().all()

    async def update_deduction_type(self, type_id: int, data: DeductionTypeUpdate) -> DeductionType:
        deduction_type = await self.session.get(DeductionType, type_id)
        if not deduction_type:
            raise HTTPException(status_code=404, detail="Deduction type not found")
        
        for field, value in data.dict(exclude_unset=True).items():
            setattr(deduction_type, field, value)
        
        await self.session.commit()
        await self.session.refresh(deduction_type)
        return deduction_type


    # ====================================== Employee Deduction CRUD =========================================== #
    async def create_employee_deduction(self, data: EmployeeDeductionCreate, created_by: int) -> EmployeeDeduction:
        # Validate employee exists
        employee = await self.session.get(Employee, data.employee_id)
        if not employee or not employee.is_active:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Validate deduction type exists
        deduction_type = await self.session.get(DeductionType, data.deduction_type_id)
        if not deduction_type or not deduction_type.is_active:
            raise HTTPException(status_code=404, detail="Deduction type not found")
        
        # Create employee deduction
        employee_deduction = EmployeeDeduction(
            **data.dict(),
            remaining_amount=data.total_amount,
            created_by=created_by,
            status=DeductionStatus.ACTIVE
        )
        
        self.session.add(employee_deduction)
        await self.session.commit()
        await self.session.refresh(employee_deduction)
        
        logger.info(f"Created deduction for employee {data.employee_id}: {data.total_amount}")
        return employee_deduction

    async def get_employee_deductions(
        self, 
        employee_id: Optional[int] = None,
        status: Optional[DeductionStatus] = None,
        active_only: bool = True
    ) -> List[EmployeeDeduction]:
        query = select(EmployeeDeduction).options(
            selectinload(EmployeeDeduction.deduction_type),
            selectinload(EmployeeDeduction.employee)
        )
        
        conditions = []
        if employee_id:
            conditions.append(EmployeeDeduction.employee_id == employee_id)
        if status:
            conditions.append(EmployeeDeduction.status == status)
        if active_only:
            conditions.append(EmployeeDeduction.status.in_([DeductionStatus.ACTIVE]))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.session.execute(query.order_by(EmployeeDeduction.created_at.desc()))
        return result.scalars().all()

    async def update_employee_deduction(self, deduction_id: int, data: EmployeeDeductionUpdate) -> EmployeeDeduction:
        deduction = await self.session.get(EmployeeDeduction, deduction_id)
        if not deduction:
            raise HTTPException(status_code=404, detail="Employee deduction not found")
        
        # Update fields
        for field, value in data.dict(exclude_unset=True).items():
            if field == 'total_amount' and value:
                # Recalculate remaining amount
                deduction.remaining_amount = value - deduction.paid_amount
            setattr(deduction, field, value)
        
        await self.session.commit()
        await self.session.refresh(deduction)
        return deduction

    async def bulk_create_deductions(self, data: BulkDeductionCreate, created_by: int) -> Dict[str, Any]:
        """Create deductions for multiple employees"""
        stats = {"successful": 0, "failed": 0, "errors": []}
        
        for employee_id in data.employee_ids:
            try:
                deduction_data = EmployeeDeductionCreate(
                    employee_id=employee_id,
                    deduction_type_id=data.deduction_type_id,
                    total_amount=data.total_amount,
                    monthly_deduction_limit=data.monthly_deduction_limit,
                    effective_from=data.effective_from,
                    effective_to=data.effective_to,
                    description=data.description
                )
                await self.create_employee_deduction(deduction_data, created_by)
                stats["successful"] += 1
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"Employee {employee_id}: {str(e)}")
        
        return stats

    # Deduction Calculation for Salary
    async def calculate_monthly_deductions(self, employee_id: int, salary_month: date) -> Tuple[Decimal, List[Dict]]:
        """Calculate total deductions for an employee for a specific month"""
        total_deduction = Decimal('0')
        deduction_details = []
        
        # Get auto-calculated deductions (late, absent)
        auto_deductions = await self._calculate_auto_deductions(employee_id, salary_month)
        total_deduction += auto_deductions['total']
        deduction_details.extend(auto_deductions['details'])
        
        # Get manual deductions (penalties, loans, etc.)
        manual_deductions = await self._calculate_manual_deductions(employee_id, salary_month)
        total_deduction += manual_deductions['total']
        deduction_details.extend(manual_deductions['details'])
        
        return total_deduction, deduction_details

    async def _calculate_auto_deductions(self, employee_id: int, salary_month: date) -> Dict:
        """Calculate automatic deductions like late and absent"""
        total = Decimal('0')
        details = []
        
        # Get deduction types for auto calculation
        auto_types = await self.session.execute(
            select(DeductionType).where(
                DeductionType.is_auto_calculated == True,
                DeductionType.is_active == True
            )
        )
        auto_type_dict = {dt.name: dt for dt in auto_types.scalars().all()}
        
        # Calculate late deductions
        if 'late' in auto_type_dict:
            late_amount = await self._calculate_late_deductions(employee_id, salary_month)
            if late_amount > 0:
                total += late_amount
                details.append({
                    'type_id': auto_type_dict['late'].id,
                    'type_name': 'Late',
                    'amount': late_amount,
                    'auto_calculated': True
                })
        
        # Calculate absent deductions
        if 'absent' in auto_type_dict:
            absent_amount = await self._calculate_absent_deductions(employee_id, salary_month)
            if absent_amount > 0:
                total += absent_amount
                details.append({
                    'type_id': auto_type_dict['absent'].id,
                    'type_name': 'Absent',
                    'amount': absent_amount,
                    'auto_calculated': True
                })
        
        return {'total': total, 'details': details}

    async def _calculate_manual_deductions(self, employee_id: int, salary_month: date) -> Dict:
        """Calculate manual deductions for the month"""
        total = Decimal('0')
        details = []
        
        # Get active employee deductions for this month
        deductions = await self.session.execute(
            select(EmployeeDeduction)
            .options(selectinload(EmployeeDeduction.deduction_type))
            .where(
                EmployeeDeduction.employee_id == employee_id,
                EmployeeDeduction.status == DeductionStatus.ACTIVE,
                EmployeeDeduction.effective_from <= salary_month,
                or_(
                    EmployeeDeduction.effective_to.is_(None),
                    EmployeeDeduction.effective_to >= salary_month
                ),
                EmployeeDeduction.remaining_amount > 0
            )
        )
        
        for deduction in deductions.scalars():
            # Calculate amount to deduct this month
            if deduction.monthly_deduction_limit:
                monthly_amount = min(deduction.monthly_deduction_limit, deduction.remaining_amount)
            else:
                monthly_amount = deduction.remaining_amount
            
            if monthly_amount > 0:
                total += monthly_amount
                details.append({
                    'employee_deduction_id': deduction.id,
                    'type_id': deduction.deduction_type_id,
                    'type_name': deduction.deduction_type.name,
                    'amount': monthly_amount,
                    'auto_calculated': False
                })
        
        return {'total': total, 'details': details}

    async def apply_deductions_to_salary(self, salary_id: int, employee_id: int, salary_month: date, deduction_details: List[Dict]):
        """Apply calculated deductions to salary and update employee deduction records"""
        
        for detail in deduction_details:
            # Create salary deduction record
            salary_deduction = SalaryDeduction(
                salary_id=salary_id,
                employee_deduction_id=detail.get('employee_deduction_id'),
                deduction_type_id=detail['type_id'],
                deducted_amount=detail['amount'],
                salary_month=salary_month
            )
            self.session.add(salary_deduction)
            
            # Update employee deduction if it's manual deduction
            if not detail.get('auto_calculated') and detail.get('employee_deduction_id'):
                employee_deduction = await self.session.get(EmployeeDeduction, detail['employee_deduction_id'])
                if employee_deduction:
                    employee_deduction.paid_amount += detail['amount']
                    employee_deduction.remaining_amount -= detail['amount']
                    
                    # Mark as completed if fully paid
                    if employee_deduction.remaining_amount <= 0:
                        employee_deduction.status = DeductionStatus.COMPLETED
        
        await self.session.commit()

    async def _calculate_late_deductions(self, employee_id: int, salary_month: date) -> Decimal:
        """Calculate late deductions for the month"""
        from calendar import monthrange
        
        # Get month range
        last_day = monthrange(salary_month.year, salary_month.month)[1]
        start_date = salary_month.replace(day=1)
        end_date = salary_month.replace(day=last_day)
        
        # Count late days
        late_count = await self.session.scalar(
            select(func.count()).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date.between(start_date, end_date),
                Attendance.status == AttendanceStatus.LATE
            )
        )
        
        # Get default amount for late deduction
        late_type = await self.session.scalar(
            select(DeductionType).where(DeductionType.name == 'late')
        )
        
        amount_per_late = late_type.default_amount if late_type else Decimal('50')
        return Decimal(late_count or 0) * amount_per_late

    async def _calculate_absent_deductions(self, employee_id: int, salary_month: date) -> Decimal:
        """Calculate absent deductions for the month"""
        from calendar import monthrange
        
        # Get month range
        last_day = monthrange(salary_month.year, salary_month.month)[1]
        start_date = salary_month.replace(day=1)
        end_date = salary_month.replace(day=last_day)
        
        # Count absent days (excluding holidays)
        absent_count = await self.session.scalar(
            select(func.count()).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date.between(start_date, end_date),
                Attendance.status == AttendanceStatus.ABSENT,
                Attendance.is_holiday == False
            )
        )
        
        if absent_count > 0:
            # Get employee basic salary
            employee = await self.session.get(Employee, employee_id)
            if employee and employee.basic_salary:
                daily_salary = employee.basic_salary / Decimal(str(last_day))
                return Decimal(absent_count) * daily_salary
        
        return Decimal('0')
