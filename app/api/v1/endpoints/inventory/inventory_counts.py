from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.inventory.inventory_count_service import InventoryCountService
from app.schemas.inventory.inventory_count import InventoryCount, InventoryCountCreate, InventoryCountItemCreate, InventoryCountUpdate
from app.models.auth.user import User
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()

@router.post("/", response_model=InventoryCount, status_code=status.HTTP_201_CREATED)
async def create_inventory_count(
    count_data: InventoryCountCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new inventory count"""
    try:
        service = InventoryCountService(db)
        count = await service.create_inventory_count(count_data, current_user.id)
        return count
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/{count_id}/items", response_model=dict)
async def add_item_to_inventory_count(
    count_id: int,
    item_data: InventoryCountItemCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Add item to existing inventory count"""
    try:
        service = InventoryCountService(db)
        success = await service.add_item_to_count(count_id, item_data, current_user.id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add item to inventory count")
        return {"message": "Item added to inventory count successfully"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Inventory count not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{count_id}/items/{item_id}")
async def remove_item_from_inventory_count(
    count_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Remove item from inventory count"""
    try:
        service = InventoryCountService(db)
        success = await service.remove_item_from_count(count_id, item_id, current_user.id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to remove item from inventory count")
        return {"message": "Item removed from inventory count successfully"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Inventory count not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=PaginatedResponse[InventoryCount])
async def get_inventory_counts(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    location_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all inventory counts with optional filters"""
    service = InventoryCountService(db)
    counts = await service.get_inventory_counts(
        page_index=page_index,
        page_size=page_size,
        location_id=location_id,
        status=status
    )
    return counts

@router.get("/{count_id}", response_model=InventoryCount)
async def get_inventory_count(
    count_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get inventory count by ID"""
    service = InventoryCountService(db)
    count = await service.get_inventory_count_by_id(count_id)
    if not count:
        raise HTTPException(status_code=404, detail="Inventory count not found")
    return count

@router.put("/{count_id}", response_model=InventoryCount)
async def update_inventory_count(
    count_id: int,
    count_data: InventoryCountUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update inventory count"""
    try:
        service = InventoryCountService(db)
        count = await service.update_inventory_count(count_id, count_data, current_user.id)
        return count
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Inventory count not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{count_id}/complete", response_model=InventoryCount)
async def complete_inventory_count(
    count_id: int,
    create_adjustments: bool = Query(True, description="Create stock adjustments for variances"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Complete inventory count and optionally create stock adjustments"""
    try:
        service = InventoryCountService(db)
        count = await service.complete_inventory_count(count_id, create_adjustments, current_user.id)
        return count
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Inventory count not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))