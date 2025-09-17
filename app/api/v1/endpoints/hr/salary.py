from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.salary_service import SalaryService
from app.services.hr.deduction_service import DeductionService
from app.schemas.hr.salary_schema import SalaryCreate, SalaryUpdate, SalaryResponse, SalaryPaymentUpdate
from app.models.auth.user import User

router = APIRouter()

@router.post("/generate/{employee_id}", response_model=SalaryResponse)
async def generate_employee_salary(
    employee_id: int,
    salary_month: date,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Generate salary for a specific employee with integrated deduction calculation"""
    service = SalaryService(session)
    return await service.generate_monthly_salary(employee_id, salary_month, current_user.id)

@router.post("/generate-bulk")
async def generate_bulk_salary(
    background_tasks: BackgroundTasks,
    salary_month: date = Query(..., description="Salary month in YYYY-MM-dd format"),
    location_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Generate salary for multiple employees with integrated deductions (background task)"""
    service = SalaryService(session)
    
    # Run as background task for large operations
    async def bulk_salary_task():
        return await service.generate_bulk_salary(salary_month, location_id, department_id, current_user.id)
    
    background_tasks.add_task(bulk_salary_task)
    return {"message": "Bulk salary generation with deduction calculation started in background"}

@router.put("/{salary_id}/mark-paid", response_model=SalaryResponse)
async def mark_salary_paid(
    salary_id: int,
    payment_data: SalaryPaymentUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Mark salary as paid"""
    service = SalaryService(session)
    return await service.mark_salary_paid(
        salary_id,
        payment_data.payment_date,
        payment_data.payment_method,
        payment_data.payment_reference,
        current_user.id
    )

@router.get("/employee/{employee_id}", response_model=PaginatedResponse[SalaryResponse])
async def get_employee_salaries(
    employee_id: int,
    page_index: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    year: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get employee salary history with pagination and deduction details"""
    service = SalaryService(session)
    return await service.get_employee_salaries(
        employee_id=employee_id,
        page_index=page_index,
        page_size=page_size,
        year=year
    )

@router.get("/reports")
async def get_salary_reports(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    location_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get salary reports for management with deduction breakdown"""
    service = SalaryService(session)
    return await service.get_salary_reports(month, year, location_id, department_id)

# New endpoints for deduction management
@router.get("/{salary_id}/deductions")
async def get_salary_deduction_details(
    salary_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get detailed deduction breakdown for a salary"""
    service = SalaryService(session)
    salary = await service.get_salary_with_deduction_details(salary_id)
    if not salary:
        raise HTTPException(status_code=404, detail="Salary not found")
    
    deduction_breakdown = []
    for deduction in salary.deduction_details:
        deduction_breakdown.append({
            "id": deduction.id,
            "type_name": deduction.deduction_type.name if deduction.deduction_type else "Unknown",
            "amount": float(deduction.deducted_amount),
            "employee_deduction_id": deduction.employee_deduction_id,
            "is_auto_calculated": deduction.deduction_type.is_auto_calculated if deduction.deduction_type else False
        })
    
    return {
        "salary_id": salary.id,
        "employee_id": salary.employee_id,
        "salary_month": salary.salary_month,
        "total_deductions": float(salary.total_deductions),
        "deduction_breakdown": deduction_breakdown
    }

@router.put("/{salary_id}/recalculate-deductions", response_model=SalaryResponse)
async def recalculate_salary_deductions(
    salary_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Recalculate deductions for an existing salary"""
    service = SalaryService(session)
    return await service.recalculate_salary_deductions(salary_id, current_user.id)

@router.get("/preview-deductions/{employee_id}")
async def preview_salary_deductions(
    employee_id: int,
    salary_month: date = Query(..., description="Salary month in YYYY-MM-dd format"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Preview deductions for an employee before generating salary"""
    deduction_service = DeductionService(session)
    total_deduction, deduction_details = await deduction_service.calculate_monthly_deductions(
        employee_id, salary_month
    )
    
    return {
        "employee_id": employee_id,
        "salary_month": salary_month,
        "total_deduction": float(total_deduction),
        "deduction_breakdown": [
            {
                "type_name": detail.get('type_name'),
                "amount": float(detail['amount']),
                "is_auto_calculated": detail.get('auto_calculated', False),
                "employee_deduction_id": detail.get('employee_deduction_id')
            }
            for detail in deduction_details
        ]
    }