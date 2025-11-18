from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.holiday_service import HolidayService
from app.schemas.hr.holiday_schema import HolidayCreate, HolidayUpdate, HolidayResponse
from app.models.auth.user import User

router = APIRouter()

@router.post("/", response_model=HolidayResponse)
async def create_holiday(
    holiday: HolidayCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("holiday", "create"))
):
    """Create a new holiday"""
    service = HolidayService(session)
    return await service.create_holiday(holiday, current_user.id)

@router.get("/", response_model=PaginatedResponse[HolidayResponse])
async def get_holidays(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    is_active: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get holidays with filtering and pagination"""
    service = HolidayService(session)
    return await service.get_holidays(
        page_index=page_index,
        page_size=page_size,
        year=year,
        month=month,
        is_active=is_active
    )

@router.get("/{holiday_id}", response_model=HolidayResponse)
async def get_holiday(
    holiday_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific holiday by ID"""
    service = HolidayService(session)
    holiday = await service.get_holiday(holiday_id)
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    return holiday

@router.put("/{holiday_id}", response_model=HolidayResponse)
async def update_holiday(
    holiday_id: int,
    holiday: HolidayUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("holiday", "update"))
):
    """Update holiday"""
    service = HolidayService(session)
    return await service.update_holiday(holiday_id, holiday, current_user.id)

@router.delete("/{holiday_id}")
async def delete_holiday(
    holiday_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("holiday", "delete"))
):
    """Delete holiday"""
    service = HolidayService(session)
    result = await service.delete_holiday(holiday_id, current_user.id)
    return {"message": "Holiday deleted successfully", "success": result}