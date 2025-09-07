from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.inventory.stock_level_service import StockLevelService
from app.schemas.inventory.stock_level import StockLevel, StockLevelCreate, StockLevelUpdate
from app.schemas.inventory.inventory_response import StockSummaryResponse
from app.models.auth.user import User
from app.core.exceptions import ValidationError

router = APIRouter()

@router.post("/", response_model=StockLevel, status_code=status.HTTP_201_CREATED)
async def create_stock_level(
    stock_level_data: StockLevelCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new stock level"""
    try:
        service = StockLevelService(db)
        stock_level = await service.create_stock_level(stock_level_data, current_user.id)
        return stock_level
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=PaginatedResponse[StockLevel])
async def get_stock_levels(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    location_id: Optional[int] = Query(None),
    item_id: Optional[int] = Query(None),
    low_stock_only: bool = Query(False),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all stock levels with optional filters"""
    service = StockLevelService(db)
    stock_levels = await service.get_stock_levels(
        page_index=page_index,
        page_size=page_size,
        location_id=location_id,
        item_id=item_id,
        low_stock_only=low_stock_only
    )
    return stock_levels

@router.get("/summary/{location_id}", response_model=StockSummaryResponse)
async def get_location_stock_summary(
    location_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get stock summary for a location"""
    service = StockLevelService(db)
    summary = await service.get_location_stock_summary(location_id)
    return summary

@router.get("/item/{item_id}/location/{location_id}", response_model=StockLevel)
async def get_stock_level_by_item_location(
    item_id: int,
    location_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get stock level for specific item and location"""
    service = StockLevelService(db)
    stock_level = await service.get_stock_level_by_item_location(item_id, location_id)
    if not stock_level:
        raise HTTPException(status_code=404, detail="Stock level not found")
    return stock_level

@router.get("/{stock_level_id}", response_model=StockLevel)
async def get_stock_level(
    stock_level_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get stock level by ID"""
    service = StockLevelService(db)
    stock_level = await service.get_stock_level_by_id(stock_level_id)
    if not stock_level:
        raise HTTPException(status_code=404, detail="Stock level not found")
    return stock_level

@router.put("/{stock_level_id}", response_model=StockLevel)
async def update_stock_level(
    stock_level_id: int,
    stock_level_data: StockLevelUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update stock level"""
    try:
        service = StockLevelService(db)
        stock_level = await service.update_stock_level(stock_level_id, stock_level_data, current_user.id)
        return stock_level
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))