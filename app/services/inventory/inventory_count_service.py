from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, desc, func
from app.models.inventory.inventory_count import InventoryCount
from app.models.inventory.inventory_count_item import InventoryCountItem
from app.models.inventory.item import Item
from app.models.inventory.stock_level import StockLevel
from app.models.organization.location import Location
from app.schemas.inventory.inventory_count import InventoryCountCreate, InventoryCountUpdate, InventoryCountItemCreate
from app.core.exceptions import NotFoundError, ValidationError
from datetime import date

class InventoryCountService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_inventory_count(self, count_data: InventoryCountCreate, current_user_id: int) -> InventoryCount:
        # Validate location exists
        location = await self.db.execute(select(Location).where(Location.id == count_data.location_id))
        if not location.scalar_one_or_none():
            raise ValidationError("Location not found")

        # Generate count number
        count_number = await self._generate_count_number()

        inventory_count = InventoryCount(
            count_number=count_number,
            location_id=count_data.location_id,
            count_date=count_data.count_date,
            count_type=count_data.count_type,
            conducted_by=current_user_id,
            notes=count_data.notes
        )
        
        self.db.add(inventory_count)
        await self.db.commit()
        await self.db.refresh(inventory_count)
        result = await self.db.execute(
            select(InventoryCount)
            .options(
                selectinload(InventoryCount.location),
                selectinload(InventoryCount.items)
                    .selectinload(InventoryCountItem.item),
                selectinload(InventoryCount.items)
                    .selectinload(InventoryCountItem.reason)
            )
            .where(InventoryCount.id == inventory_count.id)
        )
        return result.scalars().unique().one()

    async def _generate_count_number(self) -> str:
        """Generate unique count number"""
        today = date.today()
        prefix = f"IC-{today.strftime('%Y%m%d')}"
        
        result = await self.db.execute(
            select(func.count(InventoryCount.id))
            .where(InventoryCount.count_number.like(f"{prefix}%"))
        )
        count = result.scalar() + 1
        
        return f"{prefix}-{count:04d}"

    async def add_item_to_count(
        self, 
        count_id: int, 
        item_data: InventoryCountItemCreate, 
        current_user_id: int
    ) -> bool:
        """Add item to inventory count"""
        # Get inventory count
        inventory_count = await self.get_inventory_count_by_id(count_id)
        if not inventory_count:
            raise NotFoundError("Inventory count not found")

        # Check if count can be modified
        if inventory_count.status == "COMPLETED":
            raise ValidationError("Cannot add items to completed inventory count")

        # Validate item exists
        item = await self.db.execute(
            select(Item).where(Item.id == item_data.item_id)
        )
        if not item.scalar_one_or_none():
            raise ValidationError(f"Item {item_data.item_id} not found")

        # Check if item already exists in this count
        existing_item = await self.db.execute(
            select(InventoryCountItem).where(
                and_(
                    InventoryCountItem.inventory_count_id == count_id,
                    InventoryCountItem.item_id == item_data.item_id,
                    InventoryCountItem.is_deleted == False
                )
            )
        )
        if existing_item.scalar_one_or_none():
            raise ValidationError("Item already exists in this inventory count")

        # Get unit cost from item
        item_obj = await self.db.execute(
            select(Item.unit_cost).where(Item.id == item_data.item_id)
        )
        unit_cost = item_obj.scalar_one_or_none() or Decimal(0)

        # Calculate variance
        variance_quantity = item_data.counted_quantity - item_data.system_quantity
        variance_value = variance_quantity * unit_cost if unit_cost else None

        count_item = InventoryCountItem(
            inventory_count_id=count_id,
            item_id=item_data.item_id,
            system_quantity=item_data.system_quantity,
            counted_quantity=item_data.counted_quantity,
            variance_quantity=variance_quantity,
            unit_cost=unit_cost,
            variance_value=variance_value,
            expiry_date=item_data.expiry_date,
            reason_id=item_data.reason_id,
            remarks=item_data.remarks,
            created_by=current_user_id
        )
        
        self.db.add(count_item)
        await self.db.commit()
        return True

    async def remove_item_from_count(
        self, 
        count_id: int, 
        item_id: int, 
        current_user_id: int
    ) -> bool:
        """Remove item from inventory count"""
        inventory_count = await self.get_inventory_count_by_id(count_id)
        if not inventory_count:
            raise NotFoundError("Inventory count not found")

        if inventory_count.status == "COMPLETED":
            raise ValidationError("Cannot remove items from completed inventory count")

        await self.db.execute(
            InventoryCountItem.__table__.delete().where(
                and_(
                    InventoryCountItem.inventory_count_id == count_id,
                    InventoryCountItem.id == item_id
                )
            )
        )

        await self.db.commit()
        return True
    
    async def get_inventory_count_by_id(self, count_id: int) -> Optional[InventoryCount]:
        result = await self.db.execute(
            select(InventoryCount)
            .options(
                selectinload(InventoryCount.location),
                selectinload(InventoryCount.items)
                    .selectinload(InventoryCountItem.item),
                selectinload(InventoryCount.items)
                    .selectinload(InventoryCountItem.reason)
            )
            .where(InventoryCount.id == count_id)
        )
        return result.scalar_one_or_none()

    async def get_inventory_counts(
        self, 
        page_index: int = 1,
        page_size: int = 100,
        location_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get inventory counts with pagination"""
        try:
            query = select(InventoryCount).options(
                selectinload(InventoryCount.location),
                selectinload(InventoryCount.items)
                    .selectinload(InventoryCountItem.item),
                selectinload(InventoryCount.items)
                    .selectinload(InventoryCountItem.reason)
            ).order_by(desc(InventoryCount.count_date))
            
            conditions = []
            if location_id:
                conditions.append(InventoryCount.location_id == location_id)
            if status:
                conditions.append(InventoryCount.status == status)
                
            if conditions:
                query = query.where(and_(*conditions))
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar() or 0
            
            # Calculate offset and get data
            skip = (page_index - 1) * page_size
            query = query.offset(skip).limit(page_size)
            result = await self.db.execute(query)
            counts = result.scalars().all()
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": counts
            }
        except Exception as e:
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def update_inventory_count(self, count_id: int, count_data: InventoryCountUpdate, current_user_id: int) -> InventoryCount:
        inventory_count = await self.get_inventory_count_by_id(count_id)
        if not inventory_count:
            raise NotFoundError("Inventory count not found")

        # Check if count can be updated (not completed)
        if inventory_count.status == "COMPLETED":
            raise ValidationError("Cannot update completed inventory count")

        for field, value in count_data.dict(exclude_unset=True).items():
            setattr(inventory_count, field, value)
        
        inventory_count.updated_by = current_user_id
        await self.db.commit()
        await self.db.refresh(inventory_count)
        return inventory_count

    async def complete_inventory_count(self, count_id: int, create_adjustments: bool, current_user_id: int) -> InventoryCount:
        """Complete inventory count and optionally create stock adjustments"""
        inventory_count = await self.get_inventory_count_by_id(count_id)
        if not inventory_count:
            raise NotFoundError("Inventory count not found")

        if inventory_count.status == "COMPLETED":
            raise ValidationError("Inventory count already completed")

        # Create stock adjustments for variances if requested
        if create_adjustments:
            from app.services.inventory.stock_movement_service import StockMovementService
            from app.models.shared.enums import StockMovementType
            
            movement_service = StockMovementService(self.db)
            
            for item in inventory_count.items:
                if item.variance_quantity != 0:
                    # Create adjustment movement
                    await movement_service.create_stock_movement(
                        movement_data={
                            'item_id': item.item_id,
                            'location_id': inventory_count.location_id,
                            'movement_type': StockMovementType.ADJUSTMENT,
                            'quantity': abs(item.variance_quantity),
                            'unit_cost': item.unit_cost,
                            'reference_type': 'INVENTORY_COUNT',
                            'reference_id': inventory_count.id,
                            'batch_number': item.batch_number,
                            'expiry_date': item.expiry_date,
                            'remarks': f"Inventory count adjustment: {item.variance_quantity}"
                        },
                        current_user_id=current_user_id,
                        auto_update_stock=True
                    )

        inventory_count.status = "COMPLETED"
        inventory_count.verified_by = current_user_id
        inventory_count.updated_by = current_user_id

        await self.db.commit()
        await self.db.refresh(inventory_count)
        return inventory_count

    async def generate_count_sheet(self, location_id: int, item_ids: Optional[List[int]] = None) -> InventoryCountCreate:
        """Generate inventory count sheet with current system quantities"""
        # Get current stock levels for location
        query = select(StockLevel, Item).join(Item).where(
            and_(
                StockLevel.location_id == location_id,
                Item.is_active == True
            )
        )
        
        if item_ids:
            query = query.where(Item.id.in_(item_ids))
            
        result = await self.db.execute(query)
        stock_data = result.all()

        count_items = []
        for stock_level, item in stock_data:
            count_items.append(InventoryCountItemCreate(
                item_id=item.id,
                system_quantity=stock_level.current_stock,
                counted_quantity=0,  # To be filled during count
                unit_cost=item.unit_cost
            ))

        return InventoryCountCreate(
            location_id=location_id,
            count_date=date.today(),
            count_type="FULL" if not item_ids else "PARTIAL",
            items=count_items
        )