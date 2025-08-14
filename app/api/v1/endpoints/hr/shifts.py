from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_active_user
from app.core.database import get_async_session
from app.services.hr.shift_service import ShiftService
from app.schemas.hr.shift_schema import (
    ShiftTypeCreate, ShiftTypeUpdate, ShiftTypeResponse,
    UserShiftCreate, UserShiftUpdate, UserShiftResponse
)
from app.models.auth.user import User

router = APIRouter()

# Shift Type Endpoints
@router.post("/types", response_model=ShiftTypeResponse)
async def create_shift_type(
    shift_type: ShiftTypeCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new shift type"""
    service = ShiftService(session)
    return await service.create_shift_type(shift_type, current_user.id)

@router.get("/types", response_model=List[ShiftTypeResponse])
async def get_shift_types(
    is_active: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Get all shift types"""
    service = ShiftService(session)
    return await service.get_shift_types(is_active)

@router.put("/types/{shift_type_id}", response_model=ShiftTypeResponse)
async def update_shift_type(
    shift_type_id: int,
    shift_type: ShiftTypeUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """Update shift type"""
    service = ShiftService(session)
    return await service.update_shift_type(shift_type_id, shift_type, current_user.id)

# User Shift Assignment Endpoints
@router.post("/assign", response_model=UserShiftResponse)
async def assign_shift_to_employee(
    assignment: UserShiftCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user)
):
    """Assign shift to employee"""
    service = ShiftService(session)
    return await service.assign_shift_to_employee(assignment, current_user.id)

@router.get("/employee/{employee_id}/current", response_model=Optional[UserShiftResponse])
async def get_employee_current_shift(
    employee_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get employee's current shift"""
    service = ShiftService(session)
    return await service.get_employee_current_shift(employee_id)

@router.get("/employee/{employee_id}/history", response_model=List[UserShiftResponse])
async def get_employee_shift_history(
    employee_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get employee's shift history"""
    service = ShiftService(session)
    return await service.get_employee_shift_history(employee_id)