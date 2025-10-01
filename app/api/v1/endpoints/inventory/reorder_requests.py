from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict
from decimal import Decimal
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.inventory.reorder_request_service import ReorderRequestService
from app.schemas.inventory.reorder_request import ReorderRequest, ReorderRequestCreate, ReorderRequestItemCreate, ReorderRequestUpdate
from app.models.shared.enums import ReorderRequestStatus
from app.models.auth.user import User
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()

@router.post("/", response_model=ReorderRequest, status_code=status.HTTP_201_CREATED)
async def create_reorder_request(
    request_data: ReorderRequestCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new reorder request"""
    try:
        service = ReorderRequestService(db)
        request = await service.create_reorder_request(request_data, current_user.id)
        return request
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{request_id}/items", response_model=dict)
async def add_item_to_reorder_request(
    request_id: int,
    item_data: ReorderRequestItemCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Add item to existing reorder request"""
    try:
        service = ReorderRequestService(db)
        success = await service.add_item_to_reorder_request(request_id, item_data, current_user.id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add item to reorder request")
        return {"message": "Item added to reorder request successfully"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Reorder request not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{request_id}/items/{item_id}")
async def remove_item_from_reorder_request(
    request_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Remove item from reorder request"""
    try:
        service = ReorderRequestService(db)
        success = await service.remove_item_from_reorder_request(request_id, item_id, current_user.id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to remove item from reorder request")
        return {"message": "Item removed from reorder request successfully"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Reorder request not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=PaginatedResponse[ReorderRequest])
async def get_reorder_requests(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    location_id: Optional[int] = Query(None),
    status: Optional[ReorderRequestStatus] = Query(None),
    priority: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all reorder requests with optional filters"""
    service = ReorderRequestService(db)
    requests = await service.get_reorder_requests(
        page_index=page_index,
        page_size=page_size,
        location_id=location_id,
        status=status,
        priority=priority
    )
    return requests

@router.post("/auto-generate", response_model=List[ReorderRequest])
async def auto_generate_reorder_requests(
    location_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Auto-generate reorder requests for items below reorder point"""
    service = ReorderRequestService(db)
    requests = await service.auto_generate_reorder_requests(user_id=current_user.id, location_id = location_id)
    return requests

@router.get("/{request_id}", response_model=ReorderRequest)
async def get_reorder_request(
    request_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get reorder request by ID"""
    service = ReorderRequestService(db)
    request = await service.get_reorder_request_by_id(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Reorder request not found")
    return request

@router.put("/{request_id}", response_model=ReorderRequest)
async def update_reorder_request(
    request_id: int,
    request_data: ReorderRequestUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update reorder request"""
    try:
        service = ReorderRequestService(db)
        request = await service.update_reorder_request(request_id, request_data, current_user.id)
        return request
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Reorder request not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{request_id}/approve", response_model=ReorderRequest)
async def approve_reorder_request(
    request_id: int,
    approved_quantities: Dict[int, Decimal],
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Approve reorder request with specific quantities"""
    try:
        service = ReorderRequestService(db)
        request = await service.approve_reorder_request(request_id, approved_quantities, current_user.id)
        return request
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Reorder request not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{request_id}/reject", response_model=ReorderRequest)
async def reject_reorder_request(
    request_id: int,
    reason: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Reject reorder request"""
    try:
        service = ReorderRequestService(db)
        request = await service.reject_reorder_request(request_id, reason, current_user.id)
        return request
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Reorder request not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))