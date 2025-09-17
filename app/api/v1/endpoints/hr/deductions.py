from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict
from datetime import date

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.deduction_service import DeductionService
from app.schemas.hr.deduction_schema import (
    DeductionTypeCreate, DeductionTypeUpdate, DeductionTypeResponse,
    EmployeeDeductionCreate, EmployeeDeductionUpdate, EmployeeDeductionResponse,
    BulkDeductionCreate, DeductionSummaryResponse
)
from app.models.auth.user import User
from app.models.shared.enums import DeductionStatus

router = APIRouter()

# ===================================== Deduction Type Endpoints ===================================== #
@router.post("/types", response_model=DeductionTypeResponse)
async def create_deduction_type(
    data: DeductionTypeCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new deduction type"""
    service = DeductionService(session)
    return await service.create_deduction_type(data)

@router.get("/types", response_model=List[DeductionTypeResponse])
async def get_deduction_types(
    active_only: bool = Query(True),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all deduction types"""
    service = DeductionService(session)
    return await service.get_deduction_types(active_only)

@router.put("/types/{type_id}", response_model=DeductionTypeResponse)
async def update_deduction_type(
    type_id: int,
    data: DeductionTypeUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update deduction type"""
    service = DeductionService(session)
    return await service.update_deduction_type(type_id, data)

# ====================================== Employee Deduction Endpoints ================================== #
@router.post("/employee", response_model=EmployeeDeductionResponse)
async def create_employee_deduction(
    data: EmployeeDeductionCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new employee deduction"""
    service = DeductionService(session)
    return await service.create_employee_deduction(data, current_user.id)

@router.get("/employee", response_model=List[EmployeeDeductionResponse])
async def get_employee_deductions(
    employee_id: Optional[int] = Query(None),
    status: Optional[DeductionStatus] = Query(None),
    active_only: bool = Query(True),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get employee deductions with filters"""
    service = DeductionService(session)
    return await service.get_employee_deductions(employee_id, status, active_only)

@router.put("/employee/{deduction_id}", response_model=EmployeeDeductionResponse)
async def update_employee_deduction(
    deduction_id: int,
    data: EmployeeDeductionUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update employee deduction"""
    service = DeductionService(session)
    return await service.update_employee_deduction(deduction_id, data)

@router.post("/employee/bulk")
async def create_bulk_deductions(
    data: BulkDeductionCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create deductions for multiple employees"""
    service = DeductionService(session)
    
    async def bulk_deduction_task():
        return await service.bulk_create_deductions(data, current_user.id)
    
    background_tasks.add_task(bulk_deduction_task)
    return {"message": "Bulk deduction creation started in background"}

# Calculate deductions for specific employee and month
@router.get("/calculate/{employee_id}")
async def calculate_monthly_deductions(
    employee_id: int,
    salary_month: date = Query(..., description="Salary month in YYYY-MM-dd format"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Calculate deductions for an employee for specific month"""
    service = DeductionService(session)
    total_deduction, deduction_details = await service.calculate_monthly_deductions(employee_id, salary_month)
    
    return {
        "employee_id": employee_id,
        "salary_month": salary_month,
        "total_deduction": float(total_deduction),
        "deduction_breakdown": deduction_details
    }
