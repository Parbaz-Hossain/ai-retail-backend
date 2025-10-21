from datetime import date
import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Query
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.inventory.product import Product
from app.models.inventory.product_item import ProductItem
from app.schemas.common.pagination import PaginatedResponse
from app.services.inventory.product_service import ProductService
from app.schemas.inventory.product_schema import ProductResponse, ProductCreateForm, ProductUpdateForm
from app.models.auth.user import User
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_form: ProductCreateForm = Depends(),
    product_image: UploadFile = File(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new product with optional image and auto-generated QR code"""
    try:
        # Convert form to schema
        product_create = product_form.to_product_create()
        
        service = ProductService(db)
        
        # Create product with product items
        product = await service.create_product(product_create, current_user.id)
        
        # Generate unique product code: PROD-000000ProductId-TodayDate-UserId
        today = date.today().strftime("%Y-%m-%d")
        product_code = f"PROD-{product.id:07d}-{today}-{current_user.id}"
        product.product_code = product_code
        
        # Handle image upload if provided
        if product_image:
            from app.utils.file_handler import FileUploadService
            file_service = FileUploadService()
            
            # Upload image with product ID
            image_path = await file_service.save_file(product_image, "products", product.id)
            
            # Update product with image path
            product.image_url = image_path

        await db.commit()
        
        # Reload product with all relationships eagerly loaded
        result = await db.execute(
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.product_items).selectinload(ProductItem.item)
            )
            .where(Product.id == product.id)
        )
        product = result.scalars().unique().one()
        
        return product    
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create product error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product"
        )

@router.get("/", response_model=PaginatedResponse[ProductResponse])
async def get_products(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    is_available: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all products with optional filters and pagination"""
    service = ProductService(db)
    products = await service.get_products(
        page_index=page_index,
        page_size=page_size,
        search=search,
        category_id=category_id,
        is_available=is_available
    )
    return products

@router.get("/by-category/{category_id}", response_model=List[ProductResponse])
async def get_products_by_category(
    category_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get all products in a specific category"""
    service = ProductService(db)
    products = await service.get_products_by_category(category_id)
    return products

@router.get("/code/{product_code}", response_model=ProductResponse)
async def get_product_by_code(
    product_code: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get product by product code"""
    service = ProductService(db)
    product = await service.get_product_by_code(product_code)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get product by ID with all product items (ingredients)"""
    service = ProductService(db)
    product = await service.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_form: ProductUpdateForm = Depends(),
    product_image: UploadFile = File(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update product with optional image and product items"""
    try:
        service = ProductService(db)
        
        # Convert form to schema
        product_update = product_form.to_product_update()
        
        # Update product
        updated_product = await service.update_product(product_id, product_update, current_user.id)
        
        # Handle image upload if provided
        if product_image:
            from app.utils.file_handler import FileUploadService
            file_service = FileUploadService()
            
            # Upload image with product ID
            image_path = await file_service.save_file(product_image, "products", updated_product.id)
            
            # Update product with image path
            updated_product.image_url = image_path

        await db.commit()
        # Reload with relationships
        result = await db.execute(
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.product_items).selectinload(ProductItem.item)
            )
            .where(Product.id == updated_product.id)
        )
        updated_product = result.scalars().unique().one()        
        return updated_product
        
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Product not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update product error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product"
        )

@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete product (soft delete)"""
    try:
        service = ProductService(db)
        await service.delete_product(product_id, current_user.id)
        return {"message": "Product deleted successfully"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Product not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

# @router.post("/{product_id}/recalculate-cost", response_model=Product)
# async def recalculate_product_cost(
#     product_id: int,
#     db: AsyncSession = Depends(get_async_session),
#     current_user: User = Depends(get_current_user)
# ):
#     """Recalculate product cost price based on current item costs"""
#     try:
#         service = ProductService(db)
#         product = await service.recalculate_product_cost(product_id)
#         return product
#     except NotFoundError:
#         raise HTTPException(status_code=404, detail="Product not found")
#     except Exception as e:
#         logger.error(f"Recalculate cost error: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to recalculate product cost"
#         )