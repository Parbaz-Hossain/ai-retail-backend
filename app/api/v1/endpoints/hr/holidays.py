from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_active_user
from app.core.database import get_async_session
from app.services.hr.holiday_service import HolidayService
from app.schemas.hr.holiday_schema import HolidayCreate, HolidayUpdate, HolidayResponse
from app.models.auth.user import User

router = APIRouter()

@router.post("/", response_model=HolidayResponse)
async def create_holiday(
    holiday: HolidayCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new holiday"""
    service = HolidayService(session)
    return await service.create_holiday(holiday, current_user.id)

@router.get("/", response_model=List[HolidayResponse])
async def get_holidays(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    is_active: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Get holidays with filtering"""
    service = HolidayService(session)
    return await service.get_holidays(year, month, is_active)

@router.put("/{holiday_id}", response_model=HolidayResponse)
async def update_holiday(
    holiday_id: int,
    holiday: HolidayUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """Update holiday"""
    service = HolidayService(session)
    return await service.update_holiday(holiday_id, holiday, current_user.id)

@router.delete("/{holiday_id}")
async def delete_holiday(
    holiday_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """Delete holiday"""
    service = HolidayService(session)
    result = await service.delete_holiday(holiday_id, current_user.id)
    return {"message": "Holiday deleted successfully", "success": result}