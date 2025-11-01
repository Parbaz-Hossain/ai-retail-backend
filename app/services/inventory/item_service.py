from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, func, or_
from app.models.inventory.item import Item
from app.models.inventory.item_ingredient import ItemIngredient
from app.models.inventory.stock_level import StockLevel
from app.models.inventory.category import Category
from app.models.inventory.stock_type import StockType
from app.schemas.inventory.item import ItemCreate, ItemUpdate
from app.core.exceptions import NotFoundError, ValidationError
import uuid

from app.schemas.inventory.item_ingredient_schema import ItemIngredientCreate

class ItemService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_item(self, item_data: ItemCreate, current_user_id: int) -> Item:
        # Validate category exists
        if item_data.category_id:
            category = await self.db.execute(
                select(Category).where(Category.id == item_data.category_id)
            )
            if not category.scalar_one_or_none():
                raise ValidationError("Category not found")

        # Validate stock type exists
        if item_data.stock_type_id:
            stock_type = await self.db.execute(
                select(StockType).where(StockType.id == item_data.stock_type_id)
            )
            if not stock_type.scalar_one_or_none():
                raise ValidationError("Stock type not found")

        # Generate QR code if not provided
        qr_code = item_data.qr_code or f"ITEM-{uuid.uuid4().hex[:8].upper()}"

        item = Item(
            **item_data.dict(exclude={'qr_code'}),
            qr_code=qr_code
        )
        
        self.db.add(item)
        await self.db.flush()
        
        result = await self.db.execute(
                select(Item)
                .options(
                    selectinload(Item.category),
                    selectinload(Item.stock_type),
                    selectinload(Item.stock_levels)
                )
                .where(Item.id == item.id)
            )
        return result.scalars().unique().one()       

    async def get_item_by_id(self, item_id: int) -> Optional[Item]:
        result = await self.db.execute(
            select(Item)
            .options(
                selectinload(Item.category),
                selectinload(Item.stock_type),
                selectinload(Item.stock_levels).selectinload(StockLevel.location)
            )
            .where(and_(Item.id == item_id, Item.is_active == True))
        )
        return result.scalar_one_or_none()

    async def get_item_by_code(self, item_code: str) -> Optional[Item]:
        result = await self.db.execute(
            select(Item)
            .options(selectinload(Item.category), selectinload(Item.stock_type), selectinload(Item.stock_levels))
            .where(and_(Item.item_code == item_code, Item.is_active == True))
        )
        return result.scalar_one_or_none()

    async def get_items(
        self, 
        page_index: int = 1,
        page_size: int = 100,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        stock_type_id: Optional[int] = None,
        low_stock_only: bool = False
    ) -> Dict[str, Any]:
        """Get items with pagination"""
        try:
            query = select(Item).options(
                selectinload(Item.category),
                selectinload(Item.stock_type),
                selectinload(Item.stock_levels)
            ).where(Item.is_active == True)
            
            if search:
                query = query.where(
                    or_(
                        Item.name.ilike(f"%{search}%"),
                        Item.item_code.ilike(f"%{search}%"),
                        Item.description.ilike(f"%{search}%")
                    )
                )
            
            if category_id:
                query = query.where(Item.category_id == category_id)
                
            if stock_type_id:
                query = query.where(Item.stock_type_id == stock_type_id)

            if low_stock_only:
                query = query.join(StockLevel).where(
                    StockLevel.current_stock <= Item.reorder_point
                )
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar() or 0
            
            # Calculate offset and get data
            skip = (page_index - 1) * page_size
            query = query.offset(skip).limit(page_size)
            result = await self.db.execute(query)
            items = result.scalars().all()
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": items
            }
        except Exception as e:
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def add_ingredient_to_item(
        self,
        item_id: int,
        ingredient_data: ItemIngredientCreate,
        current_user_id: int
    ) -> ItemIngredient:
        """Add a single ingredient to an item"""
        
        # Validate parent item exists
        item = await self.get_item_by_id(item_id)
        if not item:
            raise NotFoundError("Item not found")
        
        # Validate ingredient item exists
        ingredient_item_result = await self.db.execute(
            select(Item).where(
                and_(
                    Item.id == ingredient_data.ingredient_item_id,
                    Item.is_active == True
                )
            )
        )
        ingredient_item = ingredient_item_result.scalar_one_or_none()
        if not ingredient_item:
            raise NotFoundError("Ingredient item not found")
        
        # Prevent self-reference
        if item_id == ingredient_data.ingredient_item_id:
            raise ValidationError("Item cannot be its own ingredient")
        
        # Check if ingredient already exists
        existing = await self.db.execute(
            select(ItemIngredient).where(
                and_(
                    ItemIngredient.item_id == item_id,
                    ItemIngredient.ingredient_item_id == ingredient_data.ingredient_item_id,
                    ItemIngredient.is_active == True
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError("This ingredient already exists for this item")
        
        # Create ingredient
        ingredient = ItemIngredient(
            item_id=item_id,
            ingredient_item_id=ingredient_data.ingredient_item_id,
            quantity=ingredient_data.quantity,
            unit_type=ingredient_data.unit_type,
            description=ingredient_data.description,
            created_by=current_user_id
        )
        
        self.db.add(ingredient)
        await self.db.commit()
        await self.db.flush()
        
        # Fetch with relationships
        result = await self.db.execute(
            select(ItemIngredient)
            .options(selectinload(ItemIngredient.ingredient_item))
            .where(ItemIngredient.id == ingredient.id)
        )
        
        return result.scalar_one()

    async def remove_ingredient_from_item(
        self,
        item_id: int,
        ingredient_id: int,
        current_user_id: int
    ) -> bool:
        """Remove a single ingredient from an item (soft delete)"""
        
        # Validate item exists
        item = await self.get_item_by_id(item_id)
        if not item:
            raise NotFoundError("Item not found")
        
        # Get ingredient
        ingredient_result = await self.db.execute(
            select(ItemIngredient).where(
                and_(
                    ItemIngredient.id == ingredient_id,
                    ItemIngredient.item_id == item_id,
                    ItemIngredient.is_active == True
                )
            )
        )
        ingredient = ingredient_result.scalar_one_or_none()
        if not ingredient:
            raise NotFoundError("Ingredient not found")
        
        # Hard delete
        await self.db.delete(ingredient)
        await self.db.commit()
        return True

    async def get_items_by_location_with_stock(self, location_id: int, include_zero: Optional[bool] = False) -> List[Item]:
        """
        Get items for dropdown (DDL) in a specific location.
        By default, returns items with available_stock > 0.
        If include_zero is True, also includes items with available_stock == 0.
        """
        query = (
            select(Item)
            .join(StockLevel)
            .options(
                selectinload(Item.category),
                selectinload(Item.stock_type),
                selectinload(Item.stock_levels)
            )
            .where(
                and_(
                    Item.is_active == True,
                    StockLevel.location_id == location_id,
                )
            )
        )

        if include_zero:
            query = query.where(StockLevel.available_stock >= 0)
        else:
            query = query.where(StockLevel.available_stock > 0)

        result = await self.db.execute(query)
        return result.scalars().unique().all()

    async def update_item(self, item_id: int, item_data: ItemUpdate, current_user_id: int) -> Item:
        item = await self.get_item_by_id(item_id)
        if not item:
            raise NotFoundError("Item not found")

        for field, value in item_data.dict(exclude_unset=True).items():
            setattr(item, field, value)
        
        item.updated_by = current_user_id
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def delete_item(self, item_id: int, current_user_id: int) -> bool:
        item = await self.get_item_by_id(item_id)
        if not item:
            raise NotFoundError("Item not found")

        # Check if item has stock movements or is in use
        from app.models.inventory.stock_movement import StockMovement
        movements_result = await self.db.execute(
            select(StockMovement).where(StockMovement.item_id == item_id).limit(1)
        )
        if movements_result.scalar_one_or_none():
            raise ValidationError("Cannot delete item with stock movement history")

        # Soft delete
        item.is_active = False
        item.is_deleted = True
        await self.db.commit()
        return True

    async def get_items_by_category(self, category_id: int) -> List[Item]:
        """Get all items in a specific category"""
        result = await self.db.execute(
            select(Item)
            .options(selectinload(Item.stock_levels))
            .options(selectinload(Item.stock_type))
            .options(selectinload(Item.category))
            .where(and_(Item.category_id == category_id, Item.is_active == True))
        )
        return result.scalars().all()

    async def get_low_stock_items(self, location_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get items that are below reorder point"""
        query = (select(Item, StockLevel)
            .join(StockLevel)
            .options(
            selectinload(StockLevel.location)  # 👈 add this
            )
            .where(
                and_(
                    Item.is_active == True,
                    StockLevel.current_stock <= Item.reorder_point
                )
            )
        )
        
        if location_id:
            query = query.where(StockLevel.location_id == location_id)
            
        result = await self.db.execute(query)
        
        low_stock_items = []
        for item, stock_level in result.all():
            low_stock_items.append({
                "item": item,
                "stock_level": stock_level,
                "shortage": item.reorder_point - stock_level.current_stock
            })
            
        return low_stock_items