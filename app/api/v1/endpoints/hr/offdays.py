from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.offday_service import OffdayService
from app.schemas.hr.offday_schema import (
    OffdayCreate, OffdayBulkCreate, OffdayUpdate,
    OffdayResponse, OffdayListResponse
)
from app.models.auth.user import User

router = APIRouter()

@router.post("/", response_model=OffdayResponse)
async def create_offday(
    offday: OffdayCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a single offday for an employee"""
    service = OffdayService(session)
    return await service.create_offday(offday, current_user.id)

@router.post("/bulk", response_model=OffdayListResponse)
async def create_bulk__offdays(
    bulk_offdays: OffdayBulkCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create multiple offdays for an employee in a month (replaces existing)"""
    service = OffdayService(session)
    return await service.create_bulk_offdays(bulk_offdays, current_user.id)

@router.get("/employee/{employee_id}", response_model=OffdayListResponse)
async def get_employee_offdays(
    employee_id: int = Path(...),
    year: int = Query(..., ge=2020),
    month: int = Query(..., ge=1, le=12),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all offdays for an employee in a specific month"""
    service = OffdayService(session)
    return await service.get_employee_offdays(employee_id, year, month)

@router.get("/", response_model=PaginatedResponse[OffdayResponse])
async def get_all__offdays(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    employee_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None, ge=2020),
    month: Optional[int] = Query(None, ge=1, le=12),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get paginated offdays with filtering"""
    service = OffdayService(session)
    return await service.get_all_offdays(
        page_index=page_index,
        page_size=page_size,
        employee_id=employee_id,
        year=year,
        month=month
    )

@router.put("/{offday_id}", response_model=OffdayResponse)
async def update__offday(
    offday_id: int = Path(...),
    offday: OffdayUpdate = ...,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update a  offday"""
    service = OffdayService(session)
    return await service.update_offday(offday_id, offday, current_user.id)

@router.delete("/{offday_id}")
async def delete__offday(
    offday_id: int = Path(...),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a single offday"""
    service = OffdayService(session)
    result = await service.delete_offday(offday_id, current_user.id)
    return {"message": " offday deleted successfully", "success": result}

@router.delete("/employee/{employee_id}/month")
async def delete_employee_month_offdays(
    employee_id: int = Path(...),
    year: int = Query(..., ge=2020),
    month: int = Query(..., ge=1, le=12),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete all offdays for an employee in a specific month"""
    service = OffdayService(session)
    result = await service.delete_employee_month_offdays(employee_id, year, month, current_user.id)
    return {"message": f"All offdays deleted for employee {employee_id} in {year}-{month}", "success": result}