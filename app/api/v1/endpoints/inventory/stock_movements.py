from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date
from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.inventory.stock_movement_service import StockMovementService
from app.schemas.inventory.stock_movement import StockMovement, StockMovementCreate
from app.schemas.inventory.inventory_response import MovementSummaryResponse
from app.models.shared.enums import StockMovementType
from app.models.auth.user import User
from app.core.exceptions import ValidationError

router = APIRouter()

@router.post("/", response_model=StockMovement, status_code=status.HTTP_201_CREATED)
async def create_stock_movement(
    movement_data: StockMovementCreate,
    auto_update_stock: bool = Query(True),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("stock_movement", "create"))
):
    """Create a new stock movement"""
    try:
        service = StockMovementService(db)
        movement = await service.create_stock_movement(movement_data, current_user.id, auto_update_stock)
        return movement
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=PaginatedResponse[StockMovement])
async def get_stock_movements(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    item_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    movement_type: Optional[StockMovementType] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all stock movements with optional filters"""
    service = StockMovementService(db)
    movements = await service.get_stock_movements(
        page_index=page_index,
        page_size=page_size,
        item_id=item_id,
        location_id=location_id,
        movement_type=movement_type,
        start_date=start_date,
        end_date=end_date
    )
    return movements

@router.get("/summary", response_model=MovementSummaryResponse)
async def get_movement_summary(
    location_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get movement summary statistics"""
    service = StockMovementService(db)
    summary = await service.get_movement_summary(location_id, start_date, end_date)
    return summary

@router.get("/item/{item_id}/history", response_model=List[StockMovement])
async def get_item_movement_history(
    item_id: int,
    location_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get movement history for a specific item"""
    service = StockMovementService(db)
    movements = await service.get_item_movement_history(item_id, location_id)
    return movements

@router.get("/{movement_id}", response_model=StockMovement)
async def get_stock_movement(
    movement_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get stock movement by ID"""
    service = StockMovementService(db)
    movement = await service.get_stock_movement_by_id(movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Stock movement not found")
    return movement