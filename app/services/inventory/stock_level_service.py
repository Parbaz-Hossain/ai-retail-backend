from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, func, or_
from app.models.inventory.stock_level import StockLevel
from app.models.inventory.item import Item
from app.models.organization.location import Location
from app.schemas.inventory.stock_level import StockLevelCreate, StockLevelUpdate
from app.core.exceptions import NotFoundError, ValidationError
from decimal import Decimal
from app.services.auth.user_service import UserService

class StockLevelService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)
        
    async def create_stock_level(self, stock_level_data: StockLevelCreate, current_user_id: int) -> StockLevel:
        # Check if combination already exists
        existing = await self.db.execute(
            select(StockLevel).where(and_(
                StockLevel.item_id == stock_level_data.item_id,
                StockLevel.location_id == stock_level_data.location_id
            ))
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Stock level already exists for this item and location")

        # Validate item and location exist
        item = await self.db.execute(select(Item).where(Item.id == stock_level_data.item_id))
        if not item.scalar_one_or_none():
            raise ValidationError("Item not found")

        location = await self.db.execute(select(Location).where(Location.id == stock_level_data.location_id))
        if not location.scalar_one_or_none():
            raise ValidationError("Location not found")

        stock_level = StockLevel(
            **stock_level_data.dict(),
            available_stock=stock_level_data.current_stock - (stock_level_data.reserved_stock or 0)
        )
        
        self.db.add(stock_level)
        await self.db.commit()
        await self.db.refresh(stock_level)
        result = await self.db.execute(
            select(StockLevel)
            .options(selectinload(StockLevel.item), selectinload(StockLevel.location))
            .where(StockLevel.id == stock_level.id)
        )
        return result.scalar_one_or_none()

    async def get_stock_level_by_id(self, stock_level_id: int) -> Optional[StockLevel]:
        result = await self.db.execute(
            select(StockLevel)
            .options(selectinload(StockLevel.item), selectinload(StockLevel.location))
            .where(StockLevel.id == stock_level_id)
        )
        return result.scalar_one_or_none()

    async def get_stock_level_by_item_location(self, item_id: int, location_id: int) -> Optional[StockLevel]:
        result = await self.db.execute(
            select(StockLevel)
            .options(selectinload(StockLevel.item), selectinload(StockLevel.location))
            .where(and_(StockLevel.item_id == item_id, StockLevel.location_id == location_id))
        )
        return result.scalar_one_or_none()

    async def get_stock_levels(
        self, 
        page_index: int = 1,
        page_size: int = 100,
        location_id: Optional[int] = None,
        item_id: Optional[int] = None,
        low_stock_only: bool = False,
        search: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get stock levels with pagination"""
        try:
            conditions = []
            
            # Search: First get matching item IDs
            if search:
                search_term = f"%{search}%"
                item_subquery = select(Item.id).where(
                    or_(
                        Item.name.ilike(search_term),
                        Item.item_code.ilike(search_term)
                    )
                )
                conditions.append(StockLevel.item_id.in_(item_subquery))

            if location_id:
                conditions.append(StockLevel.location_id == location_id)
            if item_id:
                conditions.append(StockLevel.item_id == item_id)

            # Location manager restriction
            if user_id:
                role_name = await self.user_service.get_specific_role_name_by_user(user_id, "location_manager")
                if role_name:
                    loc_res = await self.db.execute(
                        select(Location.id).where(Location.manager_id == user_id)
                    )
                    loc_ids = loc_res.scalars().all()
                    if loc_ids:
                        conditions.append(StockLevel.location_id.in_(loc_ids))
                
            # Low stock: use subquery
            if low_stock_only:
                low_stock_subquery = (
                    select(Item.id)
                    .join(StockLevel, StockLevel.item_id == Item.id)
                    .where(StockLevel.current_stock <= Item.reorder_point)
                )
                conditions.append(StockLevel.item_id.in_(low_stock_subquery))

            # Build query
            query = select(StockLevel).options(
                selectinload(StockLevel.item),
                selectinload(StockLevel.location)
            )
            
            if conditions:
                query = query.where(and_(*conditions))

            # Count
            count_query = select(func.count(StockLevel.id))
            if conditions:
                count_query = count_query.where(and_(*conditions))
            
            total_result = await self.db.execute(count_query)
            total = total_result.scalar() or 0
            
            # Pagination
            skip = (page_index - 1) * page_size
            query = query.offset(skip).limit(page_size)
            
            result = await self.db.execute(query)
            stock_levels = result.scalars().all()
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": stock_levels
            }
        except Exception as e:
            import traceback
            print(f"ERROR: {e}")
            print(traceback.format_exc())
            raise
        
    async def update_stock_level(self, stock_level_id: int, stock_level_data: StockLevelUpdate, current_user_id: int) -> StockLevel:
        stock_level = await self.get_stock_level_by_id(stock_level_id)
        if not stock_level:
            raise NotFoundError("Stock level not found")

        for field, value in stock_level_data.dict(exclude_unset=True).items():
            setattr(stock_level, field, value)
        
        # Recalculate available stock
        stock_level.available_stock = stock_level.current_stock - (stock_level.reserved_stock or 0)
        
        await self.db.commit()
        await self.db.refresh(stock_level)
        return stock_level

    async def adjust_stock(
        self, 
        item_id: int, 
        location_id: int, 
        quantity_change: Decimal, 
        reason: str,
        current_user_id: int
    ) -> StockLevel:
        """Adjust stock level by a specific amount (positive or negative)"""
        stock_level = await self.get_stock_level_by_item_location(item_id, location_id)
        
        if not stock_level:
            # Create new stock level if doesn't exist
            stock_level = StockLevel(
                item_id=item_id,
                location_id=location_id,
                current_stock=max(0, quantity_change),
                reserved_stock=0,
                available_stock=max(0, quantity_change)
            )
            self.db.add(stock_level)
        else:
            # Update existing stock level
            stock_level.current_stock += quantity_change
            stock_level.current_stock = max(0, stock_level.current_stock)  # Prevent negative stock
            stock_level.available_stock = stock_level.current_stock - (stock_level.reserved_stock or 0)

        await self.db.commit()
        await self.db.refresh(stock_level)
        return stock_level

    async def reserve_stock(
        self, 
        item_id: int, 
        location_id: int, 
        quantity: Decimal,
        current_user_id: int
    ) -> StockLevel:
        """Reserve stock for orders/transfers"""
        stock_level = await self.get_stock_level_by_item_location(item_id, location_id)
        
        if not stock_level:
            raise NotFoundError("Stock level not found")
            
        if stock_level.available_stock < quantity:
            raise ValidationError("Insufficient available stock for reservation")

        stock_level.reserved_stock = (stock_level.reserved_stock or 0) + quantity
        stock_level.available_stock = stock_level.current_stock - stock_level.reserved_stock

        await self.db.commit()
        await self.db.refresh(stock_level)
        return stock_level

    async def release_reservation(
        self, 
        item_id: int, 
        location_id: int, 
        quantity: Decimal,
        current_user_id: int
    ) -> StockLevel:
        """Release reserved stock"""
        stock_level = await self.get_stock_level_by_item_location(item_id, location_id)
        
        if not stock_level:
            raise NotFoundError("Stock level not found")

        stock_level.reserved_stock = max(0, (stock_level.reserved_stock or 0) - quantity)
        stock_level.available_stock = stock_level.current_stock - stock_level.reserved_stock

        await self.db.commit()
        await self.db.refresh(stock_level)
        return stock_level

    async def get_location_stock_summary(self, location_id: int) -> Dict[str, Any]:
        """Get stock summary for a location"""
        result = await self.db.execute(
            select(
                func.count(StockLevel.id).label('total_items'),
                func.sum(StockLevel.current_stock).label('total_stock'),
                func.sum(StockLevel.reserved_stock).label('total_reserved'),
                func.sum(StockLevel.available_stock).label('total_available')
            ).where(StockLevel.location_id == location_id)
        )
        
        summary = result.first()
        
        # Get low stock count
        low_stock_result = await self.db.execute(
            select(func.count(StockLevel.id))
            .join(Item)
            .where(and_(
                StockLevel.location_id == location_id,
                StockLevel.current_stock <= Item.reorder_point
            ))
        )
        
        low_stock_count = low_stock_result.scalar()

        return {
            "location_id": location_id,
            "total_items": summary.total_items or 0,
            "total_stock": float(summary.total_stock or 0),
            "total_reserved": float(summary.total_reserved or 0),
            "total_available": float(summary.total_available or 0),
            "low_stock_items": low_stock_count
        }