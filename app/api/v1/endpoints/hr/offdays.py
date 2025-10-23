from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.hr.offday_service import OffdayService
from app.services.approval.approval_service import ApprovalService
from app.models.shared.enums import ApprovalRequestType, ApprovalStatus
from app.schemas.hr.offday_schema import (
    OffdayCreate, OffdayBulkCreate, OffdayUpdate,
    OffdayResponse, OffdayListResponse
)
from app.models.auth.user import User

router = APIRouter()

@router.post("/")
async def create_offday(
    offday: OffdayCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a single offday - goes through approval if enabled
    """
    approval_service = ApprovalService(session)
    offday_service = OffdayService(session)
    
    # Check if approval system is enabled
    if await approval_service.is_approval_enabled():
        # Create approval request
        request_data = offday.dict()
        request_data["offday_date"] = request_data["offday_date"].isoformat()
        
        approval_request = await approval_service.create_approval_request(
            request_type=ApprovalRequestType.DAYOFF,
            employee_id=offday.employee_id,
            request_data=request_data,
            requested_by=current_user.id,
            module="HR",
            remarks=f"Offday creation request for {offday.offday_date}"
        )
        
        return {
            "message": "Offday creation sent for approval",
            "approval_request_id": approval_request.id,
            "status": "pending_approval",
            "approval_request": approval_request
        }
    else:
        # Direct creation without approval
        result = await offday_service.create_offday(offday, current_user.id)
        return {
            "message": "Offday created successfully",
            "status": "completed",
            "data": result
        }

@router.post("/bulk")
async def create_bulk_offdays(
    bulk_offdays: OffdayBulkCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create multiple offdays for an employee - goes through approval if enabled
    """
    approval_service = ApprovalService(session)
    offday_service = OffdayService(session)
    
    # Check if approval system is enabled
    if await approval_service.is_approval_enabled():
        # Create approval request
        request_data = bulk_offdays.dict()
        request_data["offday_dates"] = [d.isoformat() for d in request_data["offday_dates"]]
        
        approval_request = await approval_service.create_approval_request(
            request_type=ApprovalRequestType.DAYOFF,
            employee_id=bulk_offdays.employee_id,
            request_data=request_data,
            requested_by=current_user.id,
            module="HR",
            remarks=f"Bulk offday creation for {bulk_offdays.year}-{bulk_offdays.month}"
        )
        
        return {
            "message": "Bulk offday creation sent for approval",
            "approval_request_id": approval_request.id,
            "status": "pending_approval",
            "approval_request": approval_request
        }
    else:
        # Direct creation without approval
        result = await offday_service.create_bulk_offdays(bulk_offdays, current_user.id)
        return {
            "message": "Bulk offdays created successfully",
            "status": "completed",
            "data": result
        }

# @router.post("/approval/{approval_id}/execute")
# async def execute_approved_offday(
#     approval_id: int,
#     session: AsyncSession = Depends(get_async_session),
#     current_user: User = Depends(get_current_user)
# ):
#     """
#     Execute an approved offday creation (called after all approvals)
#     """
#     approval_service = ApprovalService(session)
#     offday_service = OffdayService(session)
    
#     # Get the approval request
#     approval_request = await approval_service.get_approval_request(approval_id)
    
#     if not approval_request:
#         raise HTTPException(status_code=404, detail="Approval request not found")
    
#     if approval_request.status != ApprovalStatus.APPROVED:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Cannot execute. Request status is {approval_request.status.value}"
#         )
    
#     # Check if already executed
#     if approval_request.reference_id:
#         raise HTTPException(status_code=400, detail="This request has already been executed")
    
#     request_data = approval_request.request_data
    
#     # Check if this is bulk or single offday
#     if "offday_dates" in request_data:
#         # Bulk offdays
#         from datetime import date
#         request_data["offday_dates"] = [
#             date.fromisoformat(d) for d in request_data["offday_dates"]
#         ]
#         bulk_create = OffdayBulkCreate(**request_data)
#         result = await offday_service.create_bulk_offdays(bulk_create, current_user.id)
        
#         # Update approval request - for bulk, store the count in reference_id
#         from sqlalchemy import update
#         from app.models.hr.approval_request import ApprovalRequest
        
#         await session.execute(
#             update(ApprovalRequest)
#             .where(ApprovalRequest.id == approval_id)
#             .values(reference_id=result.total_offdays)
#         )
#         await session.commit()
        
#         return {
#             "message": "Bulk offdays created successfully",
#             "data": result
#         }
#     else:
#         # Single offday
#         from datetime import date
#         request_data["offday_date"] = date.fromisoformat(request_data["offday_date"])
#         offday_create = OffdayCreate(**request_data)
#         result = await offday_service.create_offday(offday_create, current_user.id)
        
#         # Update approval request with reference
#         from sqlalchemy import update
#         from app.models.hr.approval_request import ApprovalRequest
        
#         await session.execute(
#             update(ApprovalRequest)
#             .where(ApprovalRequest.id == approval_id)
#             .values(reference_id=result.id)
#         )
#         await session.commit()
        
#         return {
#             "message": "Offday created successfully",
#             "data": result
#         }

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
async def get_all_offdays(
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

@router.get("/{offday_id}", response_model=OffdayResponse)
async def get_offday(
    offday_id: int = Path(...),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a single offday by ID"""
    service = OffdayService(session)
    offday = await service.get_offday(offday_id)
    if not offday:
        raise HTTPException(status_code=404, detail="Offday not found")
    return offday

@router.put("/{offday_id}")
async def update_offday(
    offday_id: int = Path(...),
    offday: OffdayUpdate = ...,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update an offday - goes through approval if enabled
    """
    approval_service = ApprovalService(session)
    offday_service = OffdayService(session)
    
    # Check if approval system is enabled
    if await approval_service.is_approval_enabled():
        # Get the existing offday to include employee_id
        existing_offday = await offday_service.get_offday(offday_id)
        
        if not existing_offday:
            raise HTTPException(status_code=404, detail="Offday not found")
        
        # Create approval request
        request_data = offday.dict(exclude_unset=True)
        request_data["offday_id"] = offday_id
        if "offday_date" in request_data and request_data["offday_date"]:
            request_data["offday_date"] = request_data["offday_date"].isoformat()
        
        approval_request = await approval_service.create_approval_request(
            request_type=ApprovalRequestType.DAYOFF,
            employee_id=existing_offday.employee_id,
            request_data=request_data,
            requested_by=current_user.id,
            module="HR",
            remarks="Offday update request"
        )
        
        return {
            "message": "Offday update sent for approval",
            "approval_request_id": approval_request.id,
            "status": "pending_approval",
            "approval_request": approval_request
        }
    else:
        # Direct update without approval
        result = await offday_service.update_offday(offday_id, offday, current_user.id)
        return {
            "message": "Offday updated successfully",
            "status": "completed",
            "data": result
        }

@router.delete("/{offday_id}")
async def delete_offday(
    offday_id: int = Path(...),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a single offday"""
    service = OffdayService(session)
    result = await service.delete_offday(offday_id, current_user.id)
    return {"message": "Offday deleted successfully", "success": result}

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