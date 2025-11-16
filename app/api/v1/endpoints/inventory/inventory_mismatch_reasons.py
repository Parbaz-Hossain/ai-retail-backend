from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.inventory.inventory_mismatch_reason_service import InventoryMismatchReasonService
from app.schemas.inventory.inventory_mismatch_reason import (
    InventoryMismatchReason,
    InventoryMismatchReasonCreate,
    InventoryMismatchReasonUpdate
)
from app.models.auth.user import User
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()

@router.post("/", response_model=InventoryMismatchReason, status_code=status.HTTP_201_CREATED)
async def create_mismatch_reason(
    reason_data: InventoryMismatchReasonCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("mismatch_reason", "create"))
):
    """Create a new inventory mismatch reason"""
    try:
        service = InventoryMismatchReasonService(db)
        reason = await service.create_reason(reason_data, current_user.id)
        return reason
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=PaginatedResponse[InventoryMismatchReason])
async def get_all_mismatch_reasons(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all mismatch reasons"""
    service = InventoryMismatchReasonService(db)
    reasons = await service.get_all_reasons(
        page_index=page_index, 
        page_size=page_size, 
        search=search
    )
    return reasons

@router.get("/{reason_id}", response_model=InventoryMismatchReason)
async def get_mismatch_reason(
    reason_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get mismatch reason by ID"""
    service = InventoryMismatchReasonService(db)
    reason = await service.get_reason_by_id(reason_id)
    if not reason:
        raise HTTPException(status_code=404, detail="Mismatch reason not found")
    return reason

@router.put("/{reason_id}", response_model=InventoryMismatchReason)
async def update_mismatch_reason(
    reason_id: int,
    reason_data: InventoryMismatchReasonUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("mismatch_reason", "update"))
):
    """Update mismatch reason"""
    try:
        service = InventoryMismatchReasonService(db)
        reason = await service.update_reason(reason_id, reason_data, current_user.id)
        return reason
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Mismatch reason not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{reason_id}")
async def delete_mismatch_reason(
    reason_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("mismatch_reason", "delete"))
):
    """Delete mismatch reason"""
    try:
        service = InventoryMismatchReasonService(db)
        await service.delete_reason(reason_id, current_user.id)
        return {"message": "Mismatch reason deleted successfully"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Mismatch reason not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))