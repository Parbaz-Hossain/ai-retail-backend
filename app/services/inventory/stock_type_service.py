from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_
from app.models.inventory.stock_type import StockType
from app.schemas.inventory.stock_type import StockTypeCreate, StockTypeUpdate
from app.core.exceptions import NotFoundError, ValidationError

class StockTypeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_stock_type(self, stock_type_data: StockTypeCreate, current_user_id: int) -> StockType:
        # Check for duplicate name
        existing = await self.db.execute(
            select(StockType).where(StockType.name == stock_type_data.name)
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Stock type name already exists")

        stock_type = StockType(
            **stock_type_data.dict(),
            created_by=current_user_id
        )
        
        self.db.add(stock_type)
        await self.db.commit()
        await self.db.refresh(stock_type)
        return stock_type

    async def get_stock_type_by_id(self, stock_type_id: int) -> Optional[StockType]:
        result = await self.db.execute(
            select(StockType).where(and_(StockType.id == stock_type_id, StockType.is_active == True))
        )
        return result.scalar_one_or_none()

    async def get_stock_types(self, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[StockType]:
        query = select(StockType).where(StockType.is_active == True)
        
        if search:
            query = query.where(
                or_(
                    StockType.name.ilike(f"%{search}%"),
                    StockType.description.ilike(f"%{search}%")
                )
            )
        
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_stock_type(self, stock_type_id: int, stock_type_data: StockTypeUpdate, current_user_id: int) -> StockType:
        result =  await self.db.execute(
            select(StockType).where(and_(StockType.id == stock_type_id, StockType.is_deleted == False))
        )
        stock_type = result.scalar_one_or_none()
        if not stock_type:
            raise NotFoundError("Stock type not found")

        # Check for duplicate name if being changed
        if stock_type_data.name and stock_type_data.name != stock_type.name:
            existing = await self.db.execute(
                select(StockType).where(and_(
                    StockType.name == stock_type_data.name,
                    StockType.id != stock_type_id
                ))
            )
            if existing.scalar_one_or_none():
                raise ValidationError("Stock type name already exists")

        for field, value in stock_type_data.dict(exclude_unset=True).items():
            setattr(stock_type, field, value)
        
        stock_type.updated_by = current_user_id
        await self.db.commit()
        await self.db.refresh(stock_type)
        return stock_type

    async def delete_stock_type(self, stock_type_id: int, current_user_id: int) -> bool:
        stock_type = await self.get_stock_type_by_id(stock_type_id)
        if not stock_type:
            raise NotFoundError("Stock type not found")

        # Check if stock type has items
        from app.models.inventory.item import Item
        items_result = await self.db.execute(
            select(Item).where(Item.stock_type_id == stock_type_id).limit(1)
        )
        if items_result.scalar_one_or_none():
            raise ValidationError("Cannot delete stock type with associated items")

        # Soft delete
        stock_type.is_active = False
        stock_type.is_deleted = True
        stock_type.updated_by = current_user_id
        await self.db.commit()
        return True