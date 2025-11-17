from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.shift_service import ShiftService
from app.services.approval.approval_service import ApprovalService
from app.models.shared.enums import ApprovalRequestType
from app.schemas.hr.shift_schema import (
    EmployeeShiftDetail, EmployeeShiftSummary, ShiftTypeCreate, 
    ShiftTypeUpdate, ShiftTypeResponse,
    UserShiftCreate, UserShiftUpdate, UserShiftResponse
)
from app.models.hr.user_shift import UserShift
from app.models.auth.user import User

router = APIRouter()

# region Shift Type Endpoints

@router.post("/types", response_model=ShiftTypeResponse)
async def create_shift_type(
    shift_type: ShiftTypeCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("shift_type", "create"))
):
    """Create a new shift type"""
    service = ShiftService(session)
    return await service.create_shift_type(shift_type, current_user.id)

@router.get("/types", response_model=PaginatedResponse[ShiftTypeResponse])
async def get_shift_types(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all shift types with pagination"""
    service = ShiftService(session)
    return await service.get_shift_types(
        page_index=page_index,
        page_size=page_size,
        is_active=is_active
    )

@router.get("/types/{shift_type_id}", response_model=ShiftTypeResponse)
async def get_shift_type(
    shift_type_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific shift type by ID"""
    service = ShiftService(session)
    shift_type = await service.get_shift_type(shift_type_id)
    if not shift_type:
        raise HTTPException(status_code=404, detail="Shift type not found")
    return shift_type

@router.put("/types/{shift_type_id}", response_model=ShiftTypeResponse)
async def update_shift_type(
    shift_type_id: int,
    shift_type: ShiftTypeUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("shift_type", "update"))
):
    """Update shift type"""
    service = ShiftService(session)
    return await service.update_shift_type(shift_type_id, shift_type, current_user.id)

@router.get("/employee/{employee_id}/current", response_model=Optional[UserShiftResponse])
async def get_employee_current_shift(
    employee_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get employee's current shift"""
    service = ShiftService(session)
    return await service.get_employee_current_shift(employee_id)

# endregion 

# region User Shift Endpoints with Approval System

@router.post("/assign")
async def assign_shift_to_employee(
    assignment: UserShiftCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("shift", "assign"))
):
    """
    Assign shift to employee - goes through approval system if enabled
    """
    approval_service = ApprovalService(session)
    shift_service = ShiftService(session)
    
    # Check if approval system is enabled for HR.SHIFT
    if await approval_service.is_approval_enabled("HR", ApprovalRequestType.SHIFT):
        # Create approval request
        request_data = assignment.dict()
        approval_request = await approval_service.create_approval_request(
            request_type=ApprovalRequestType.SHIFT,
            employee_id=assignment.employee_id,
            request_data=request_data,
            requested_by=current_user.id,
            module="HR",
            remarks="Shift assignment request"
        )
        
        return {
            "message": "Shift assignment sent for approval",
            "approval_request_id": approval_request.id,
            "status": "pending_approval",
            "approval_request": approval_request
        }
    else:
        # Direct assignment without approval
        user_shift = await shift_service.assign_shift_to_employee(assignment, current_user.id)
        return {
            "message": "Shift assigned successfully",
            "status": "completed",
            "data": user_shift
        }

@router.put("/assign/{user_shift_id}")
async def update_user_shift(
    user_shift_id: int,
    shift_update: UserShiftUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("shift", "update"))
):
    """
    Update user shift assignment - goes through approval system if enabled
    """
    approval_service = ApprovalService(session)
    shift_service = ShiftService(session)
    
    # Check if approval system is enabled for HR.SHIFT
    if await approval_service.is_approval_enabled("HR", ApprovalRequestType.SHIFT):
        # Get the existing shift to include employee_id
        result = await session.execute(
            select(UserShift).where(UserShift.id == user_shift_id)
        )
        existing_shift = result.scalar_one_or_none()
        
        if not existing_shift:
            raise HTTPException(status_code=404, detail="Shift not found")
        
        # Create approval request
        request_data = shift_update.dict(exclude_unset=True)
        request_data["user_shift_id"] = user_shift_id
        
        approval_request = await approval_service.create_approval_request(
            request_type=ApprovalRequestType.SHIFT,
            employee_id=existing_shift.employee_id,
            request_data=request_data,
            requested_by=current_user.id,
            module="HR",
            remarks="Shift update request"
        )
        
        return {
            "message": "Shift update sent for approval",
            "approval_request_id": approval_request.id,
            "status": "pending_approval",
            "approval_request": approval_request
        }
    else:
        # Direct update without approval
        updated_shift = await shift_service.update_user_shift(
            user_shift_id, shift_update, current_user.id
        )
        return {
            "message": "Shift updated successfully",
            "status": "completed",
            "data": updated_shift
        }

@router.get("/employees/shifts", response_model=PaginatedResponse[EmployeeShiftSummary])
async def get_employee_shifts(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by employee name or ID"),
    start_date: Optional[date] = Query(None, description="Filter by effective_date >= start_date"),
    end_date: Optional[date] = Query(None, description="Filter by effective_date <= end_date"),
    is_active: Optional[bool] = Query(None, description="Filter by employee active status"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get employee shifts summary grouped by employee"""
    service = ShiftService(session)
    return await service.get_employee_shifts(
        page_index=page_index,
        page_size=page_size,
        search=search,
        start_date=start_date,
        end_date=end_date,
        is_active=is_active
    )

@router.get("/employees/{employee_id}/shifts/detail", response_model=EmployeeShiftDetail)
async def get_employee_shift_details(
    employee_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get detailed shift information for a specific employee"""
    service = ShiftService(session)
    detail = await service.get_employee_shift_details(employee_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Employee shift details not found")
    return detail

# endregion