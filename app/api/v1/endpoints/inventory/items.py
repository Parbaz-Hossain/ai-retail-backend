from datetime import date
import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_async_session
from app.schemas.common.pagination import PaginatedResponse
from app.schemas.inventory.item_ingredient_schema import ItemIngredientCreate, ItemIngredientResponse
from app.services.inventory.item_service import ItemService
from app.schemas.inventory.item import Item, ItemCreateForm, ItemUpdateForm, ItemWithIngredient
from app.schemas.inventory.stock_level import LowStockItem
from app.models.auth.user import User
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=Item, status_code=status.HTTP_201_CREATED)
async def create_item(
    item_form: ItemCreateForm = Depends(),
    item_image: UploadFile = File(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("item", "create"))
):
    """Create a new item with optional image and auto-generated QR code"""
    try:
        # Convert form to schema
        item_create = item_form.to_item_create()
        
        service = ItemService(db)
        
        # Create item first
        item = await service.create_item(item_create, current_user.id)
        
        # Generate unique item code: SKU-000000ItemId-TodayDate-UserId
        today = date.today().strftime("%Y-%m-%d")
        item_code = f"SKU-{item.id:07d}-{today}-{current_user.id}"
        item.item_code = item_code
        
        # Handle image upload if provided
        if item_image:
            from app.utils.file_handler import FileUploadService
            file_service = FileUploadService()
            
            # Upload image with item ID
            image_path = await file_service.save_file(item_image, "items", item.id)
            
            # Update item with image path
            item.image_url = image_path
        
        # Generate QR code for the item
        from app.utils.qr_generator import QRCodeService
        qr_service = QRCodeService(db)
        
        item_data_for_qr = {
            "item_code": item.item_code,
            "name": item.name,
            "category": item.category.name if item.category else None
        }
        
        qr_code_record = await qr_service.create_item_qr_code(
            item.id, 
            item_data_for_qr, 
            current_user.id
        )
        
        # Update item with QR code
        item.qr_code = qr_code_record.qr_code

        await db.commit()
        await db.refresh(item, ["category", "stock_type", "stock_levels", "updated_at"])
        return item
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create item error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create item"
        )

@router.get("/", response_model=PaginatedResponse[Item])
async def get_items(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    stock_type_id: Optional[int] = Query(None),
    low_stock_only: bool = Query(False),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
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

@router.post("/{item_id}/ingredients", response_model=ItemIngredientResponse, status_code=status.HTTP_201_CREATED)
async def add_ingredient_to_item(
    item_id: int,
    ingredient_data: ItemIngredientCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("item", "create"))
):
    """Add a single ingredient to an item"""
    try:
        service = ItemService(db)
        ingredient = await service.add_ingredient_to_item(item_id, ingredient_data, current_user.id)
        return ingredient
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Item not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Add ingredient error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add ingredient"
        )

@router.delete("/{item_id}/ingredients/{ingredient_id}")
async def remove_ingredient_from_item(
    item_id: int,
    ingredient_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("item", "delete"))
):
    """Remove a single ingredient from an item"""
    try:
        service = ItemService(db)
        await service.remove_ingredient_from_item(item_id, ingredient_id, current_user.id)
        return {"message": "Ingredient removed successfully"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Item or ingredient not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Remove ingredient error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove ingredient"
        )

@router.get("/by-location/{location_id}/dropdown", response_model=List[Item])
async def get_items_by_location_for_dropdown(
    location_id: int,
    include_zero_stock: Optional[bool] = Query(False, description="Include items with zero stock"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get items available in a specific location with stock > 0 (for dropdown)"""
    service = ItemService(db)
    items = await service.get_items_by_location_with_stock(location_id, include_zero_stock)
    return items

@router.get("/low-stock", response_model=List[LowStockItem])
async def get_low_stock_items(
    location_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get items that are below reorder point"""
    service = ItemService(db)
    low_stock_items = await service.get_low_stock_items(location_id)
    return low_stock_items

@router.get("/by-category/{category_id}", response_model=List[Item])
async def get_items_by_category(
    category_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all items in a specific category"""
    service = ItemService(db)
    items = await service.get_items_by_category(category_id)
    return items

@router.get("/code/{item_code}", response_model=Item)
async def get_item_by_code(
    item_code: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get item by item code"""
    service = ItemService(db)
    item = await service.get_item_by_code(item_code)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.get("/{item_id}", response_model=ItemWithIngredient)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get item by ID with ingredients"""
    service = ItemService(db)
    item = await service.get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.put("/{item_id}", response_model=Item)
async def update_item(
    item_id: int,
    item_form: ItemUpdateForm = Depends(),
    item_image: UploadFile = File(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("item", "update"))
):
    """Update item with optional image"""
    try:
        service = ItemService(db)
        
        # Convert form to schema
        item_update = item_form.to_item_update()
        
        # Update item first
        updated_item = await service.update_item(item_id, item_update, current_user.id)
        
        # Handle image upload if provided
        if item_image:
            from app.utils.file_handler import FileUploadService
            file_service = FileUploadService()
            
            # Upload image with item ID
            image_path = await file_service.save_file(item_image, "items", updated_item.id)
            
            # Update item with image path
            updated_item.image_url = image_path
            await db.commit()
            await db.refresh(updated_item, ["category", "stock_type", "stock_levels", "updated_at"])
        
        return updated_item
        
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Item not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update item error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update item"
        )

@router.delete("/{item_id}")
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    _permission = Depends(require_permission("item", "delete"))
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