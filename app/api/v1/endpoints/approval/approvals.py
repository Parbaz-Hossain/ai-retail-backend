import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.hr.employee import Employee
from app.schemas.common.pagination import PaginatedResponse
from app.services.approval.approval_service import ApprovalService
from app.services.auth.user_service import UserService
from app.schemas.approval.approval_member_schema import (
    ApprovalMemberCreate,
    ApprovalMemberResponse,
    ApprovalMemberUpdate
)
from app.schemas.approval.approval_request_schema import (
    ApprovalRequestResponse,
    ApprovalActionRequest
)
from app.schemas.approval.approval_settings_schema import (
    ApprovalSettingsCreate,
    ApprovalSettingsResponse
)
from app.models.shared.enums import ApprovalStatus, ApprovalRequestType
from app.models.auth.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

# region ========== Approval Settings ==========

@router.get("/settings", response_model=List[ApprovalSettingsResponse])
async def get_approval_settings(
    module: Optional[str] = Query(None, description="Filter by module"),
    action_type: Optional[ApprovalRequestType] = Query(None, description="Filter by action type"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get approval settings grouped by module"""
    service = ApprovalService(session)
    return await service.get_approval_settings(
        module=module,
        action_type=action_type     
    )

@router.get("/settings/{setting_id}", response_model=ApprovalSettingsResponse)
async def get_approval_setting(
    setting_id: int = Path(...),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get specific approval setting by ID"""
    service = ApprovalService(session)
    setting = await service.get_approval_setting(setting_id) 
    
    if not setting:
        raise HTTPException(status_code=404, detail="Approval setting not found")
    
    return setting

@router.post("/settings", response_model=ApprovalSettingsResponse)
async def create_or_update_approval_setting(
    setting: ApprovalSettingsCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create or update approval setting for specific module and action type (HR Manager only)"""
    user_service = UserService(session)
    user_role_names = await user_service.get_role_names_by_user(current_user.id)
    
    if "hr_manager" not in user_role_names:
        raise HTTPException(
            status_code=403,
            detail="Only HR Managers can update approval settings"
        )

    service = ApprovalService(session)
    return await service.create_or_update_approval_setting(setting, current_user.id)

# endregion

# region ========== Approval Members ==========

@router.post("/members", response_model=ApprovalMemberResponse)
async def add_approval_member(
    member: ApprovalMemberCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Add approval member for specific module and action types (HR Manager only)"""
    user_service = UserService(session)
    user_role_names = await user_service.get_role_names_by_user(current_user.id)
    
    if "hr_manager" not in user_role_names:
        raise HTTPException(
            status_code=403,
            detail="Only HR Managers can add approval members"
        )
    
    service = ApprovalService(session)
    return await service.add_approval_member(member, current_user.id)

@router.put("/members/{member_id}", response_model=ApprovalMemberResponse)
async def update_approval_member(
    member_id: int = Path(...),
    member_update: ApprovalMemberUpdate = ...,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update approval member (HR Manager only)"""
    user_service = UserService(session)
    user_role_names = await user_service.get_role_names_by_user(current_user.id)
    
    if "hr_manager" not in user_role_names:
        raise HTTPException(
            status_code=403,
            detail="Only HR Managers can update approval members"
        )
    
    service = ApprovalService(session)
    return await service.update_approval_member(member_id, member_update, current_user.id)

@router.delete("/members/{member_id}")
async def remove_approval_member(
    member_id: int = Path(...),
    module: str = Query(..., description="Module to remove member from"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Remove approval member (HR Manager only)"""
    user_service = UserService(session)
    user_role_names = await user_service.get_role_names_by_user(current_user.id)
    
    if "hr_manager" not in user_role_names:
        raise HTTPException(
            status_code=403,
            detail="Only HR Managers can remove approval members"
        )
    
    service = ApprovalService(session)
    success = await service.remove_approval_member(member_id, module, current_user.id)
    return {
        "message": f"Approval member removed successfully from {module} module",
        "success": success
    }

@router.get("/members", response_model=PaginatedResponse[ApprovalMemberResponse])
async def get_approval_members(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    module: Optional[str] = Query(None, description="Filter by module"),
    action_type: Optional[ApprovalRequestType] = Query(None, description="Filter by action type"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get paginated list of approval members"""
    service = ApprovalService(session)
    return await service.get_approval_members(
        page_index=page_index,
        page_size=page_size,
        module=module,
        action_type=action_type,
        is_active=is_active
    )

@router.get("/members/{member_id}", response_model=ApprovalMemberResponse)
async def get_approval_member(
    member_id: int = Path(...),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get specific approval member by ID"""
    service = ApprovalService(session)
    member = await service.get_approval_member(member_id)
    
    if not member:
        raise HTTPException(status_code=404, detail="Approval member not found")
    
    return member

# endregion

# region ========== Approval Requests ==========

@router.get("/requests", response_model=PaginatedResponse[ApprovalRequestResponse])
async def get_all_approval_requests(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    status: Optional[ApprovalStatus] = Query(None),
    request_type: Optional[ApprovalRequestType] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all approval requests with filtering"""
    service = ApprovalService(session)
    return await service.get_all_approval_requests(
        status=status,
        request_type=request_type,
        page_index=page_index,
        page_size=page_size
    )

@router.get("/requests/{request_id}", response_model=ApprovalRequestResponse)
async def get_approval_request(
    request_id: int = Path(...),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific approval request"""
    service = ApprovalService(session)
    request = await service.get_approval_request(request_id)
    
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    return request

@router.get("/requests/pending/my-approvals")
async def get_my_pending_approvals(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get pending approval requests for the current user"""
    service = ApprovalService(session)
    
    # Get employee_id for current user    
    emp_result = await session.execute(
        select(Employee.id).where(Employee.user_id == current_user.id)
    )
    employee_id = emp_result.scalar_one_or_none()
    
    if not employee_id:
        return []
    
    requests = await service.get_pending_approvals_for_member(employee_id)
    return requests

@router.post("/requests/{request_id}/respond", response_model=ApprovalRequestResponse)
async def respond_to_approval_request(
    request_id: int = Path(...),
    action: ApprovalActionRequest = ...,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Approve or reject an approval request"""
    service = ApprovalService(session)
    
    # Get employee_id for current user    
    emp_result = await session.execute(
        select(Employee.id).where(Employee.user_id == current_user.id)
    )
    employee_id = emp_result.scalar_one_or_none()
    
    if not employee_id:
        raise HTTPException(
            status_code=403,
            detail="You must be an employee to respond to approvals"
        )
    
    return await service.process_approval_response(
        request_id=request_id,
        member_employee_id=employee_id,
        action=action.action,
        user_id=current_user.id,
        comments=action.comments
    )

# endregion