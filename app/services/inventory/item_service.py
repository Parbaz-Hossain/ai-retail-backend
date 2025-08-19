from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_
from app.models.inventory.item import Item
from app.models.inventory.stock_level import StockLevel
from app.models.inventory.category import Category
from app.models.inventory.stock_type import StockType
from app.schemas.inventory.item import ItemCreate, ItemUpdate
from app.core.exceptions import NotFoundError, ValidationError
import uuid

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

        # Check for duplicate item code
        existing = await self.db.execute(
            select(Item).where(Item.item_code == item_data.item_code)
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Item code already exists")

        # Generate QR code if not provided
        qr_code = item_data.qr_code or f"ITEM-{uuid.uuid4().hex[:8].upper()}"

        item = Item(
            **item_data.dict(exclude={'qr_code'}),
            qr_code=qr_code,
            created_by=current_user_id,
            updated_by=current_user_id
        )
        
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

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
            .options(selectinload(Item.category), selectinload(Item.stock_type))
            .where(and_(Item.item_code == item_code, Item.is_active == True))
        )
        return result.scalar_one_or_none()

    async def get_items(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        stock_type_id: Optional[int] = None,
        low_stock_only: bool = False
    ) -> List[Item]:
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
            # Join with stock levels to filter low stock items
            query = query.join(StockLevel).where(
                StockLevel.current_stock <= Item.reorder_point
            )
        
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_item(self, item_id: int, item_data: ItemUpdate, current_user_id: int) -> Item:
        item = await self.get_item_by_id(item_id)
        if not item:
            raise NotFoundError("Item not found")

        # Check for duplicate item code if being changed
        if item_data.item_code and item_data.item_code != item.item_code:
            existing = await self.db.execute(
                select(Item).where(and_(
                    Item.item_code == item_data.item_code,
                    Item.id != item_id
                ))
            )
            if existing.scalar_one_or_none():
                raise ValidationError("Item code already exists")

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
        item.updated_by = current_user_id
        await self.db.commit()
        return True

    async def get_items_by_category(self, category_id: int) -> List[Item]:
        """Get all items in a specific category"""
        result = await self.db.execute(
            select(Item)
            .options(selectinload(Item.stock_levels))
            .where(and_(Item.category_id == category_id, Item.is_active == True))
        )
        return result.scalars().all()

    async def get_low_stock_items(self, location_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get items that are below reorder point"""
        query = select(Item, StockLevel).join(StockLevel).where(
            and_(
                Item.is_active == True,
                StockLevel.current_stock <= Item.reorder_point
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