import decimal
from app.schemas.common.pagination import PaginatedResponse
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Text
from datetime import date

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_async_session
from app.services.hr.deduction_service import DeductionService
from app.schemas.hr.deduction_schema import (
    DeductionTypeCreate, DeductionTypeUpdate, DeductionTypeResponse,
    EmployeeDeductionCreate, EmployeeDeductionUpdate, EmployeeDeductionResponse,
    BulkDeductionCreate
)
from app.models.auth.user import User
from app.models.shared.enums import DeductionStatus

router = APIRouter()

# region ===================================== Deduction Type Endpoints ===================================== #

@router.post("/types", response_model=DeductionTypeResponse)
async def create_deduction_type(
    data: DeductionTypeCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("deduction_type", "create"))
):
    """Create a new deduction type"""
    service = DeductionService(session)
    return await service.create_deduction_type(data)

@router.get("/types", response_model=PaginatedResponse[DeductionTypeResponse])
async def get_deduction_types(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all deduction types"""
    service = DeductionService(session)
    return await service.get_deduction_types(
        page_index=page_index,
        page_size=page_size,         
        is_active=is_active,
        search=search
    )

@router.get("/types/{type_id}", response_model=DeductionTypeResponse)
async def get_deduction_type(
    type_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific deduction type by ID"""
    service = DeductionService(session)
    return await service.get_deduction_type(type_id)

@router.put("/types/{type_id}", response_model=DeductionTypeResponse)
async def update_deduction_type(
    type_id: int,
    data: DeductionTypeUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("deduction_type", "update"))
):
    """Update deduction type"""
    service = DeductionService(session)
    return await service.update_deduction_type(type_id, data)

# endregion

# region ====================================== Employee Deduction Endpoints ================================== #

@router.post("/employee", response_model=EmployeeDeductionResponse)
async def create_employee_deduction(
    data: EmployeeDeductionCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("employee_deduction", "create"))
):
    """Create a new employee deduction"""
    service = DeductionService(session)
    return await service.create_employee_deduction(data, current_user.id)

@router.get("/employee", response_model=PaginatedResponse[EmployeeDeductionResponse])
async def get_employee_deductions(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    employee_id: Optional[int] = Query(None),
    status: Optional[DeductionStatus] = Query(None),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get employee deductions with filters"""
    service = DeductionService(session)
    return await service.get_employee_deductions(
        page_index=page_index,
        page_size=page_size, 
        employee_id=employee_id, 
        status=status,
        search=search,
        user_id=current_user.id
    )

@router.get("/employee/{deduction_id}", response_model=EmployeeDeductionResponse)
async def get_employee_deduction(
    deduction_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific employee deduction by ID"""
    service = DeductionService(session)
    return await service.get_employee_deduction(deduction_id)

@router.put("/employee/{deduction_id}", response_model=EmployeeDeductionResponse)
async def update_employee_deduction(
    deduction_id: int,
    data: EmployeeDeductionUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("employee_deduction", "update"))
):
    """Update employee deduction"""
    service = DeductionService(session)
    return await service.update_employee_deduction(deduction_id, data)

@router.post("/employee/bulk")
async def create_bulk_deductions(
    data: BulkDeductionCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("employee_deduction", "create"))
):
    """Create deductions for multiple employees"""
    service = DeductionService(session)
    
    async def bulk_deduction_task():
        return await service.bulk_create_deductions(data, current_user.id)
    
    background_tasks.add_task(bulk_deduction_task)
    return {"message": "Bulk deduction creation started in background"}

@router.put("/employee/{deduction_id}/forgive", response_model=EmployeeDeductionResponse)
async def forgive_employee_deduction(
    deduction_id: int,
    forgive_amount: decimal.Decimal,
    reason: Optional[Text] = None,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("employee_deduction", "update"))
):
    """Forgive a specific amount from an employee deduction"""
    service = DeductionService(session)
    return await service.forgive_employee_deduction(deduction_id, forgive_amount, reason, current_user.id)

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

# endregion