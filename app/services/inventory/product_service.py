from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, func, or_
from decimal import Decimal
from app.models.inventory.product import Product
from app.models.inventory.product_item import ProductItem
from app.models.inventory.item import Item
from app.models.inventory.category import Category
from app.schemas.inventory.product_schema import ProductCreate, ProductUpdate, ProductItemCreate
from app.core.exceptions import NotFoundError, ValidationError
import uuid

class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _calculate_cost_price(self, product_items: List[ProductItemCreate]) -> Decimal:
        """Calculate total cost price from product items"""
        total_cost = Decimal('0.00')
        
        for product_item in product_items:
            # Get item's current unit cost
            item_result = await self.db.execute(
                select(Item).where(Item.id == product_item.item_id)
            )
            item = item_result.scalar_one_or_none()
            
            if not item:
                raise ValidationError(f"Item with id {product_item.item_id} not found")
            
            # Use provided unit_cost or item's current unit_cost
            unit_cost = product_item.unit_cost or item.unit_cost or Decimal('0.00')
            item_cost = unit_cost * product_item.quantity
            total_cost += item_cost
        
        return total_cost

    async def _validate_product_items(self, product_items: List[ProductItemCreate]):
        """Validate that all items exist and are active"""
        for product_item in product_items:
            item_result = await self.db.execute(
                select(Item).where(
                    and_(
                        Item.id == product_item.item_id,
                        Item.is_active == True
                    )
                )
            )
            item = item_result.scalar_one_or_none()
            if not item:
                raise ValidationError(f"Item with id {product_item.item_id} not found or inactive")

    async def create_product(self, product_data: ProductCreate, current_user_id: int) -> Product:
        """Create a new product with product items (ingredients)"""
        # Validate category exists
        if product_data.category_id:
            category = await self.db.execute(
                select(Category).where(Category.id == product_data.category_id)
            )
            if not category.scalar_one_or_none():
                raise ValidationError("Category not found")

        cost_price = Decimal('0.00')

        # Generate QR code
        qr_code = f"PROD-{uuid.uuid4().hex[:8].upper()}"

        # Create product
        product = Product(
            **product_data.dict(exclude={'product_items'}),
            qr_code=qr_code,
            cost_price=cost_price
        )
        
        self.db.add(product)
        await self.db.flush()
        
        # Return product with relationships loaded
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.product_items).selectinload(ProductItem.item)
            )
            .where(Product.id == product.id)
        )
        return result.scalars().unique().one()

    async def get_product_by_id(self, product_id: int) -> Optional[Product]:
        """Get product by ID with all relationships"""
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.product_items).selectinload(ProductItem.item)
            )
            .where(and_(Product.id == product_id, Product.is_active == True))
        )
        return result.scalar_one_or_none()

    async def get_product_by_code(self, product_code: str) -> Optional[Product]:
        """Get product by product code"""
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.product_items).selectinload(ProductItem.item)
            )
            .where(and_(Product.product_code == product_code, Product.is_active == True))
        )
        return result.scalar_one_or_none()

    async def get_products(
        self,
        page_index: int = 1,
        page_size: int = 100,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        is_available: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get products with pagination and filters"""
        try:
            query = select(Product).options(
                selectinload(Product.category),
                selectinload(Product.product_items).selectinload(ProductItem.item)
            ).where(Product.is_active == True)
            
            if search:
                query = query.where(
                    or_(
                        Product.name.ilike(f"%{search}%"),
                        Product.product_code.ilike(f"%{search}%"),
                        Product.description.ilike(f"%{search}%")
                    )
                )
            
            if category_id:
                query = query.where(Product.category_id == category_id)
            
            if is_available is not None:
                query = query.where(Product.is_available == is_available)
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar() or 0
            
            # Calculate offset and get data
            skip = (page_index - 1) * page_size
            query = query.offset(skip).limit(page_size)
            result = await self.db.execute(query)
            products = result.scalars().unique().all()
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": products
            }
        except Exception as e:
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def get_products_by_category(self, category_id: int) -> List[Product]:
        """Get all products in a specific category"""
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.product_items).selectinload(ProductItem.item)
            )
            .where(and_(Product.category_id == category_id, Product.is_active == True))
        )
        return result.scalars().unique().all()

    async def update_product(
        self, 
        product_id: int, 
        product_data: ProductUpdate, 
        current_user_id: int
    ) -> Product:
        """Update product and optionally replace product items"""
        product = await self.get_product_by_id(product_id)
        if not product:
            raise NotFoundError("Product not found")

        # Validate category if being updated
        if product_data.category_id:
            category = await self.db.execute(
                select(Category).where(Category.id == product_data.category_id)
            )
            if not category.scalar_one_or_none():
                raise ValidationError("Category not found")

        # Update product fields
        for field, value in product_data.dict(exclude_unset=True, exclude={'product_items'}).items():
            setattr(product, field, value)
        
        product.updated_by = current_user_id
        await self.db.commit()
        
        # Reload with relationships
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.category),
                selectinload(Product.product_items).selectinload(ProductItem.item)
            )
            .where(Product.id == product.id)
        )
        return result.scalars().unique().one()

    async def delete_product(self, product_id: int, current_user_id: int) -> bool:
        """Soft delete product"""
        product = await self.get_product_by_id(product_id)
        if not product:
            raise NotFoundError("Product not found")

        # Soft delete
        product.is_active = False
        product.is_deleted = True
        product.updated_by = current_user_id
        await self.db.commit()
        return True