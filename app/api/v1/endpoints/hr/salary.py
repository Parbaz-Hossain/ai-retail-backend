from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.salary_service import SalaryService
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
    """Generate salary for a specific employee"""
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
    """Generate salary for multiple employees (background task)"""
    service = SalaryService(session)
    
    # Run as background task for large operations
    async def bulk_salary_task():
        return await service.generate_bulk_salary(salary_month, location_id, department_id, current_user.id)
    
    background_tasks.add_task(bulk_salary_task)
    return {"message": "Bulk salary generation started in background"}

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
    """Get employee salary history with pagination"""
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
    """Get salary reports for management"""
    service = SalaryService(session)
    return await service.get_salary_reports(month, year, location_id, department_id)
