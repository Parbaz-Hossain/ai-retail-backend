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
from app.models.shared.enums import DeductionStatus, AttendanceStatus
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

    async def get_deduction_types(
        self, 
        page_index: int = 1,
        page_size: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
        ) -> Dict[str, Any]:
        """Get paginated list of deduction types with optional active filter"""

        conditions = []
        if is_active is not None:
            conditions.append(DeductionType.is_active == is_active)

        if search:
            like = f"%{search}%"
            conditions.append(DeductionType.name.ilike(like))

        # Get total count
        total_count = await self.session.scalar(
            select(func.count(DeductionType.id)).where(*conditions)
        )
        
        # Calculate offset
        skip = (page_index - 1) * page_size
        
        # Get paginated data
        deduction_types = await self.session.scalars(
            select(DeductionType)
            .where(*conditions)
            .offset(skip)
            .limit(page_size)
        )
        return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": deduction_types.all()
            }

    async def get_deduction_type(self, type_id: int) -> DeductionType:
        deduction_type = await self.session.get(DeductionType, type_id)
        if not deduction_type:
            raise HTTPException(status_code=404, detail="Deduction type not found")
        return deduction_type

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
        employee = await self.session.get(Employee, data.employee_id)
        if not employee or not employee.is_active:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        deduction_type = await self.session.get(DeductionType, data.deduction_type_id)
        if not deduction_type or not deduction_type.is_active:
            raise HTTPException(status_code=404, detail="Deduction type not found")
        
        employee_deduction = EmployeeDeduction(
            **data.dict(),
            remaining_amount=data.total_amount,
            created_by=created_by,
            status=DeductionStatus.ACTIVE
        )
        
        self.session.add(employee_deduction)
        await self.session.commit()
        await self.session.refresh(employee_deduction, attribute_names=["deduction_type", "employee"])
        
        logger.info(f"Created deduction for employee {data.employee_id}: {data.total_amount}")
        return employee_deduction

    async def get_employee_deductions(
        self, 
        page_index: int = 1,
        page_size: int = 100,
        employee_id: Optional[int] = None,
        status: Optional[DeductionStatus] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get paginated list of employee deduction with filtering"""

        conditions = []
        if employee_id:
            conditions.append(EmployeeDeduction.employee_id == employee_id)
        if status:
            conditions.append(EmployeeDeduction.status == status)

        if search:
            like = f"%{search}%"
            conditions.append(
                    or_(
                        EmployeeDeduction.deduction_type.has(DeductionType.name.ilike(like)),
                        Employee.first_name.ilike(like),
                        Employee.last_name.ilike(like)
                    )
                )
                
        # Get total count
        total_count = await self.session.scalar(
            select(func.count(EmployeeDeduction.id)).where(*conditions)
        )
        
        # Calculate offset
        skip = (page_index - 1) * page_size
        
        # Get paginated data
        employee_deductions = await self.session.scalars(
            select(EmployeeDeduction)
            .options(
                selectinload(EmployeeDeduction.deduction_type),
                selectinload(EmployeeDeduction.employee)
            )
            .where(*conditions)
            .offset(skip)
            .limit(page_size)
        )
        return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": employee_deductions.all()
            }

    async def get_employee_deduction(self, deduction_id: int) -> EmployeeDeduction:
        deduction = await self.session.get(EmployeeDeduction, deduction_id, options=[
            selectinload(EmployeeDeduction.deduction_type),
            selectinload(EmployeeDeduction.employee)
        ])
        if not deduction:
            raise HTTPException(status_code=404, detail="Employee deduction not found")
        return deduction

    async def update_employee_deduction(self, deduction_id: int, data: EmployeeDeductionUpdate) -> EmployeeDeduction:
        deduction = await self.session.get(EmployeeDeduction, deduction_id)
        if not deduction:
            raise HTTPException(status_code=404, detail="Employee deduction not found")
        
        for field, value in data.dict(exclude_unset=True).items():
            if field == 'total_amount' and value:
                deduction.remaining_amount = value - deduction.paid_amount
            setattr(deduction, field, value)
        
        await self.session.commit()
        await self.session.refresh(deduction, attribute_names=["deduction_type", "employee", "updated_at"])
        return deduction

    async def bulk_create_deductions(self, data: BulkDeductionCreate, created_by: int) -> Dict[str, Any]:
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

    # ====================================== MAIN CALCULATION METHOD =========================================== #
    async def calculate_monthly_deductions(self, employee_id: int, salary_month: date) -> Tuple[Decimal, List[Dict]]:
        """
        Calculate total deductions for an employee for a specific month.
        Handles both existing deductions (manual + carryover auto) and new auto-deductions.
        """
        total_deduction = Decimal('0')
        deduction_details = []
        
        # 1. Process existing active deductions (manual + previous auto with remaining balance)
        existing_deductions = await self._get_active_employee_deductions(employee_id, salary_month)
        
        for deduction in existing_deductions:
            if deduction.remaining_amount > 0:
                # Apply monthly limit
                if deduction.monthly_deduction_limit:
                    monthly_amount = min(deduction.monthly_deduction_limit, deduction.remaining_amount)
                else:
                    monthly_amount = deduction.remaining_amount
                
                if monthly_amount > 0:
                    total_deduction += monthly_amount
                    deduction_details.append({
                        'employee_deduction_id': deduction.id,
                        'type_id': deduction.deduction_type_id,
                        'type_name': deduction.deduction_type.name,
                        'amount': monthly_amount,
                        'auto_calculated': deduction.deduction_type.is_auto_calculated,
                        'source': 'existing_deduction'
                    })
        
        # 2. Calculate and create new auto-deductions for current month
        new_auto_deductions = await self._calculate_and_create_new_auto_deductions(
            employee_id, salary_month
        )
        
        total_deduction += new_auto_deductions['total']
        deduction_details.extend(new_auto_deductions['details'])
        
        return total_deduction, deduction_details

    async def _get_active_employee_deductions(self, employee_id: int, salary_month: date) -> List[EmployeeDeduction]:
        """Get all active deductions for employee that should be processed this month"""
        result = await self.session.execute(
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
            .order_by(EmployeeDeduction.effective_from)
        )
        return result.scalars().all()

    async def _calculate_and_create_new_auto_deductions(self, employee_id: int, salary_month: date) -> Dict:
        """
        Calculate new auto-deductions (absent, late) for current month and create EmployeeDeduction records.
        This is the KEY method that handles your scenario!
        """
        total = Decimal('0')
        details = []
        
        # Get auto-calculation deduction types
        auto_types_result = await self.session.execute(
            select(DeductionType).where(
                DeductionType.is_auto_calculated == True,
                DeductionType.is_active == True
            )
        )
        auto_types = {dt.name: dt for dt in auto_types_result.scalars().all()}
        
        # Calculate and create ABSENT deduction
        if 'absent' in auto_types:
            absent_amount = await self._calculate_absent_deductions(employee_id, salary_month)
            if absent_amount > 0:
                # Get employee's monthly limit preference for absent deductions
                monthly_limit = await self._get_employee_auto_deduction_limit(
                    employee_id, 'absent'
                )
                
                # Create EmployeeDeduction record for this absent deduction
                absent_deduction = EmployeeDeduction(
                    employee_id=employee_id,
                    deduction_type_id=auto_types['absent'].id,
                    total_amount=absent_amount,
                    paid_amount=Decimal('0'),
                    remaining_amount=absent_amount,
                    monthly_deduction_limit=monthly_limit,  # This controls carryover!
                    effective_from=salary_month,
                    status=DeductionStatus.ACTIVE,
                    description=f"Absent deduction for {salary_month.strftime('%B %Y')}"
                )
                
                self.session.add(absent_deduction)
                await self.session.flush()  # Get ID immediately
                
                # Calculate amount to deduct THIS month
                if monthly_limit:
                    current_month_amount = min(monthly_limit, absent_amount)
                else:
                    current_month_amount = absent_amount
                
                total += current_month_amount
                details.append({
                    'employee_deduction_id': absent_deduction.id,
                    'type_id': auto_types['absent'].id,
                    'type_name': 'absent',
                    'amount': current_month_amount,
                    'auto_calculated': True,
                    'source': 'new_auto_calculation'
                })
        
        # Calculate and create LATE deduction (same logic)
        if 'late' in auto_types:
            late_amount = await self._calculate_late_deductions(employee_id, salary_month)
            if late_amount > 0:
                monthly_limit = await self._get_employee_auto_deduction_limit(
                    employee_id, 'late'
                )
                
                late_deduction = EmployeeDeduction(
                    employee_id=employee_id,
                    deduction_type_id=auto_types['late'].id,
                    total_amount=late_amount,
                    paid_amount=Decimal('0'),
                    remaining_amount=late_amount,
                    monthly_deduction_limit=monthly_limit,
                    effective_from=salary_month,
                    status=DeductionStatus.ACTIVE,
                    description=f"Late deduction for {salary_month.strftime('%B %Y')}"
                )
                
                self.session.add(late_deduction)
                await self.session.flush()
                
                current_month_amount = min(monthly_limit, late_amount) if monthly_limit else late_amount
                
                total += current_month_amount
                details.append({
                    'employee_deduction_id': late_deduction.id,
                    'type_id': auto_types['late'].id,
                    'type_name': 'late',
                    'amount': current_month_amount,
                    'auto_calculated': True,
                    'source': 'new_auto_calculation'
                })
        
        return {'total': total, 'details': details}

    async def _get_employee_auto_deduction_limit(self, employee_id: int, deduction_type_name: str) -> Optional[Decimal]:
        """
        Get employee's monthly limit for auto-deductions.
        
        You can implement this by:
        1. Adding columns to employees table
        2. Creating employee_deduction_limits table
        """
        
        
        # Query the monthly_deduction_limit from EmployeeDeduction by joining DeductionType on name
        result = await self.session.scalar(
            select(EmployeeDeduction.monthly_deduction_limit)
            .join(DeductionType, EmployeeDeduction.deduction_type_id == DeductionType.id)
            .where(
            EmployeeDeduction.employee_id == employee_id,
            DeductionType.name == deduction_type_name
            )
        )
        return result
        
    async def apply_deductions_to_salary(
        self, 
        salary_id: int, 
        employee_id: int, 
        salary_month: date, 
        deduction_details: List[Dict]
    ):
        """Apply calculated deductions to salary and update EmployeeDeduction balances"""
        
        for detail in deduction_details:
            # 1. Create salary_deductions record (audit trail)
            salary_deduction = SalaryDeduction(
                salary_id=salary_id,
                employee_deduction_id=detail['employee_deduction_id'],
                deduction_type_id=detail['type_id'],
                deducted_amount=detail['amount'],
                salary_month=salary_month
            )
            self.session.add(salary_deduction)
            
            # 2. Update EmployeeDeduction balance
            employee_deduction = await self.session.get(
                EmployeeDeduction, detail['employee_deduction_id']
            )
            if employee_deduction:
                employee_deduction.paid_amount += detail['amount']
                employee_deduction.remaining_amount -= detail['amount']
                
                # Mark as completed if fully paid
                if employee_deduction.remaining_amount <= 0:
                    employee_deduction.status = DeductionStatus.COMPLETED
                    employee_deduction.remaining_amount = Decimal('0')  # Ensure no negative
        
        await self.session.commit()
        logger.info(f"Applied {len(deduction_details)} deductions to salary {salary_id}")

    # Helper methods for calculating actual deduction amounts
    async def _calculate_late_deductions(self, employee_id: int, salary_month: date) -> Decimal:
        from calendar import monthrange
        
        last_day = monthrange(salary_month.year, salary_month.month)[1]
        start_date = salary_month.replace(day=1)
        end_date = salary_month.replace(day=last_day)
        
        late_count = await self.session.scalar(
            select(func.count()).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date.between(start_date, end_date),
                Attendance.status == AttendanceStatus.LATE
            )
        )
        
        late_type = await self.session.scalar(
            select(DeductionType).where(DeductionType.name.ilike('late'))
        )
        
        amount_per_late = late_type.default_amount if late_type else Decimal('50')
        return Decimal(late_count or 0) * amount_per_late

    async def _calculate_absent_deductions(self, employee_id: int, salary_month: date) -> Decimal:
        from calendar import monthrange
        
        last_day = monthrange(salary_month.year, salary_month.month)[1]
        start_date = salary_month.replace(day=1)
        end_date = salary_month.replace(day=last_day)
        
        absent_count = await self.session.scalar(
            select(func.count()).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date.between(start_date, end_date),
                Attendance.status == AttendanceStatus.ABSENT,
                Attendance.is_holiday == False
            )
        )
        
        if absent_count and absent_count > 0:
            employee = await self.session.get(Employee, employee_id)
            if employee and employee.basic_salary:
                daily_salary = employee.basic_salary / Decimal(str(last_day))
                return Decimal(absent_count) * daily_salary
        
        return Decimal('0')
