from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_active_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.attendance_service import AttendanceService
from app.schemas.hr.attendance_schema import AttendanceCreate, AttendanceUpdate, AttendanceResponse
from app.models.shared.enums import AttendanceStatus
from app.models.auth.user import User

router = APIRouter()

@router.post("/mark", response_model=AttendanceResponse)
async def mark_attendance(
    attendance: AttendanceCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """Mark employee attendance (check-in/check-out)"""
    service = AttendanceService(session)
    return await service.mark_attendance(attendance)

@router.get("/", response_model=PaginatedResponse[AttendanceResponse])
async def get_attendance(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    employee_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    status: Optional[AttendanceStatus] = Query(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Get attendance records with filtering and pagination"""
    service = AttendanceService(session)
    return await service.get_attendance(
        page_index=page_index,
        page_size=page_size,
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        status=status
    )

@router.get("/employee/{employee_id}/summary")
async def get_employee_attendance_summary(
    employee_id: int,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020),
    session: AsyncSession = Depends(get_async_session)
):
    """Get employee attendance summary for a month"""
    service = AttendanceService(session)
    return await service.get_employee_attendance_summary(employee_id, month, year)

@router.post("/process-daily")
async def process_daily_attendance(
    process_date: date,
    session: AsyncSession = Depends(get_async_session),
):
    """Process daily attendance (AI automation)"""
    service = AttendanceService(session)
    return await service.process_daily_attendance(process_date)