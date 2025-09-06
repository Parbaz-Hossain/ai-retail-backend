from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.inventory.item_service import ItemService
from app.schemas.inventory.item import Item, ItemCreate, ItemUpdate
from app.schemas.inventory.stock_level import LowStockItem
from app.models.auth.user import User
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()

@router.post("/", response_model=Item, status_code=status.HTTP_201_CREATED)
async def create_item(
    item_data: ItemCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new item"""
    try:
        service = ItemService(db)
        item = await service.create_item(item_data, current_user.id)
        return item
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=PaginatedResponse[Item])
async def get_items(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    stock_type_id: Optional[int] = Query(None),
    low_stock_only: bool = Query(False),
    db: AsyncSession = Depends(get_async_session)
):
    """Get all items with optional filters"""
    service = ItemService(db)
    items = await service.get_items(
        page_index=page_index,
        page_size=page_size,
        search=search,
        category_id=category_id,
        stock_type_id=stock_type_id,
        low_stock_only=low_stock_only
    )
    return items

@router.get("/low-stock", response_model=List[LowStockItem])
async def get_low_stock_items(
    location_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_async_session)
):
    """Get items that are below reorder point"""
    service = ItemService(db)
    low_stock_items = await service.get_low_stock_items(location_id)
    return low_stock_items

@router.get("/by-category/{category_id}", response_model=List[Item])
async def get_items_by_category(
    category_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    """Get all items in a specific category"""
    service = ItemService(db)
    items = await service.get_items_by_category(category_id)
    return items

@router.get("/code/{item_code}", response_model=Item)
async def get_item_by_code(
    item_code: str,
    db: AsyncSession = Depends(get_async_session)
):
    """Get item by item code"""
    service = ItemService(db)
    item = await service.get_item_by_code(item_code)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.get("/{item_id}", response_model=Item)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    """Get item by ID"""
    service = ItemService(db)
    item = await service.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.put("/{item_id}", response_model=Item)
async def update_item(
    item_id: int,
    item_data: ItemUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update item"""
    try:
        service = ItemService(db)
        item = await service.update_item(item_id, item_data, current_user.id)
        return item
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Item not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{item_id}")
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete item (soft delete)"""
    try:
        service = ItemService(db)
        await service.delete_item(item_id, current_user.id)
        return {"message": "Item deleted successfully"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Item not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))