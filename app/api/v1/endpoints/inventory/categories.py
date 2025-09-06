from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.services.inventory.category_service import CategoryService
from app.schemas.inventory.category import Category, CategoryCreate, CategoryUpdate
from app.models.auth.user import User
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()

@router.post("/", response_model=Category, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new category"""
    try:
        service = CategoryService(db)
        category = await service.create_category(category_data, current_user.id)
        return category
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=PaginatedResponse[Category])
async def get_categories(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session)
):
    """Get all categories with optional search"""
    service = CategoryService(db)
    categories = await service.get_categories(
        page_index=page_index, 
        page_size=page_size, 
        search=search
    )
    return categories

@router.get("/root", response_model=List[Category])
async def get_root_categories(
    db: AsyncSession = Depends(get_async_session)
):
    """Get root level categories (no parent)"""
    service = CategoryService(db)
    categories = await service.get_root_categories()
    return categories

@router.get("/{category_id}", response_model=Category)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    """Get category by ID"""
    try:
        service = CategoryService(db)
        category = await service.get_category_by_id(category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        return category
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Category not found")

@router.put("/{category_id}", response_model=Category)
async def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update category"""
    try:
        service = CategoryService(db)
        category = await service.update_category(category_id, category_data, current_user.id)
        return category
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Category not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete category (soft delete)"""
    try:
        service = CategoryService(db)
        await service.delete_category(category_id, current_user.id)
        return {"message": "Category deleted successfully"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Category not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))