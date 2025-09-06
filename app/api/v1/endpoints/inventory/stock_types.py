from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.inventory.stock_type_service import StockTypeService
from app.schemas.inventory.stock_type import StockType, StockTypeCreate, StockTypeUpdate
from app.models.auth.user import User
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()

@router.post("/", response_model=StockType, status_code=status.HTTP_201_CREATED)
async def create_stock_type(
    stock_type_data: StockTypeCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new stock type"""
    try:
        service = StockTypeService(db)
        stock_type = await service.create_stock_type(stock_type_data, current_user.id)
        return stock_type
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=PaginatedResponse[StockType])
async def get_stock_types(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session)
):
    """Get all stock types with optional search"""
    service = StockTypeService(db)
    stock_types = await service.get_stock_types(
        page_index=page_index, 
        page_size=page_size, 
        search=search
    )
    return stock_types

@router.get("/{stock_type_id}", response_model=StockType)
async def get_stock_type(
    stock_type_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    """Get stock type by ID"""
    service = StockTypeService(db)
    stock_type = await service.get_stock_type_by_id(stock_type_id)
    if not stock_type:
        raise HTTPException(status_code=404, detail="Stock type not found")
    return stock_type

@router.put("/{stock_type_id}", response_model=StockType)
async def update_stock_type(
    stock_type_id: int,
    stock_type_data: StockTypeUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update stock type"""
    try:
        service = StockTypeService(db)
        stock_type = await service.update_stock_type(stock_type_id, stock_type_data, current_user.id)
        return stock_type
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Stock type not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{stock_type_id}")
async def delete_stock_type(
    stock_type_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete stock type (soft delete)"""
    try:
        service = StockTypeService(db)
        await service.delete_stock_type(stock_type_id, current_user.id)
        return {"message": "Stock type deleted successfully"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Stock type not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))