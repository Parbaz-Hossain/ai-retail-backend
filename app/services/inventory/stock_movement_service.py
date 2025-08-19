from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, desc, func, cast, Date
from app.models.inventory.stock_movement import StockMovement
from app.models.inventory.item import Item
from app.models.organization.location import Location
from app.schemas.inventory.stock_movement import StockMovementCreate
from app.schemas.inventory.inventory_response import MovementSummaryResponse
from app.core.exceptions import NotFoundError, ValidationError
from app.models.shared.enums import StockMovementType
from datetime import datetime, date, timedelta

class StockMovementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_stock_movement(
        self, 
        movement_data: StockMovementCreate, 
        current_user_id: int,
        auto_update_stock: bool = True
    ) -> StockMovement:
        """Create a new stock movement"""
        
        # Validate item and location exist
        item = await self.db.execute(select(Item).where(Item.id == movement_data.item_id))
        if not item.scalar_one_or_none():
            raise ValidationError("Item not found")

        location = await self.db.execute(select(Location).where(Location.id == movement_data.location_id))
        if not location.scalar_one_or_none():
            raise ValidationError("Location not found")

        # Validate quantity is positive
        if movement_data.quantity <= 0:
            raise ValidationError("Quantity must be greater than zero")

        # Calculate total cost if not provided
        total_cost = movement_data.total_cost
        if not total_cost and movement_data.unit_cost:
            total_cost = movement_data.unit_cost * movement_data.quantity

        stock_movement = StockMovement(
            **movement_data.dict(exclude={'total_cost'}),
            total_cost=total_cost,
            performed_by=current_user_id,
            movement_date=datetime.utcnow(),
            created_by=current_user_id,
            updated_by=current_user_id
        )
        
        self.db.add(stock_movement)

        # Update stock levels if auto_update_stock is True
        if auto_update_stock:
            await self._update_stock_level_for_movement(stock_movement, current_user_id)

        await self.db.commit()
        await self.db.refresh(stock_movement)
        return stock_movement

    async def get_stock_movements(
        self,
        skip: int = 0,
        limit: int = 100,
        item_id: Optional[int] = None,
        location_id: Optional[int] = None,
        movement_type: Optional[StockMovementType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[StockMovement]:
        """Get all stock movements with optional filters"""
        
        query = select(StockMovement).options(
            selectinload(StockMovement.item),
            selectinload(StockMovement.location)
        )
        
        # Apply filters
        conditions = []
        
        if item_id:
            conditions.append(StockMovement.item_id == item_id)
        
        if location_id:
            conditions.append(StockMovement.location_id == location_id)
        
        if movement_type:
            conditions.append(StockMovement.movement_type == movement_type)
        
        if start_date:
            conditions.append(cast(StockMovement.movement_date, Date) >= start_date)
        
        if end_date:
            conditions.append(cast(StockMovement.movement_date, Date) <= end_date)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(StockMovement.movement_date)).offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_stock_movement_by_id(self, movement_id: int) -> Optional[StockMovement]:
        """Get stock movement by ID"""
        result = await self.db.execute(
            select(StockMovement)
            .options(selectinload(StockMovement.item), selectinload(StockMovement.location))
            .where(StockMovement.id == movement_id)
        )
        return result.scalar_one_or_none()

    async def get_item_movement_history(
        self, 
        item_id: int, 
        location_id: Optional[int] = None
    ) -> List[StockMovement]:
        """Get movement history for a specific item"""
        
        # First validate item exists
        item = await self.db.execute(select(Item).where(Item.id == item_id))
        if not item.scalar_one_or_none():
            raise NotFoundError("Item not found")
        
        query = select(StockMovement).options(
            selectinload(StockMovement.item),
            selectinload(StockMovement.location)
        ).where(StockMovement.item_id == item_id)
        
        if location_id:
            query = query.where(StockMovement.location_id == location_id)
        
        query = query.order_by(desc(StockMovement.movement_date))
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_movement_summary(
        self,
        location_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> MovementSummaryResponse:
        """Get movement summary statistics"""
        
        # Base query
        base_query = select(StockMovement)
        conditions = []
        
        if location_id:
            conditions.append(StockMovement.location_id == location_id)
        
        if start_date:
            conditions.append(cast(StockMovement.movement_date, Date) >= start_date)
        
        if end_date:
            conditions.append(cast(StockMovement.movement_date, Date) <= end_date)
        
        if conditions:
            base_query = base_query.where(and_(*conditions))
        
        # Total movements count
        total_movements_result = await self.db.execute(
            select(func.count(StockMovement.id)).select_from(
                base_query.subquery()
            )
        )
        total_movements = total_movements_result.scalar()
        
        # Movements by type
        movements_by_type_result = await self.db.execute(
            select(
                StockMovement.movement_type,
                func.count(StockMovement.id).label('count'),
                func.sum(StockMovement.quantity).label('total_quantity'),
                func.sum(StockMovement.total_cost).label('total_cost')
            )
            .where(and_(*conditions) if conditions else True)
            .group_by(StockMovement.movement_type)
        )
        
        movements_by_type = {}
        for row in movements_by_type_result:
            movements_by_type[row.movement_type.value] = {
                'count': int(row.count),
                'total_quantity': float(row.total_quantity) if row.total_quantity else 0,
                'total_cost': float(row.total_cost) if row.total_cost else 0
            }
        
        # Recent movements (last 5)
        recent_movements_result = await self.db.execute(
            select(StockMovement)
            .options(selectinload(StockMovement.item), selectinload(StockMovement.location))
            .where(and_(*conditions) if conditions else True)
            .order_by(desc(StockMovement.movement_date))
            .limit(5)
        )
        recent_movements = recent_movements_result.scalars().all()
        
        # Top items by movement volume
        top_items_result = await self.db.execute(
            select(
                StockMovement.item_id,
                Item.name,
                func.sum(StockMovement.quantity).label('total_quantity'),
                func.count(StockMovement.id).label('movement_count')
            )
            .join(Item, StockMovement.item_id == Item.id)
            .where(and_(*conditions) if conditions else True)
            .group_by(StockMovement.item_id, Item.name)
            .order_by(desc(func.sum(StockMovement.quantity)))
            .limit(10)
        )
        
        top_items = []
        for row in top_items_result:
            top_items.append({
                'item_id': row.item_id,
                'item_name': row.name,
                'total_quantity': float(row.total_quantity),
                'movement_count': int(row.movement_count)
            })
        
        # Calculate total value
        total_value_result = await self.db.execute(
            select(func.sum(StockMovement.total_cost))
            .where(and_(*conditions) if conditions else True)
        )
        total_value = total_value_result.scalar() or 0
        
        return MovementSummaryResponse(
            total_movements=total_movements,
            movements_by_type=movements_by_type,
            recent_movements=recent_movements,
            top_items=top_items,
            total_value=float(total_value),
            period_start=start_date,
            period_end=end_date
        )

    async def get_movements_by_reference(
        self, 
        reference_type: str, 
        reference_id: int
    ) -> List[StockMovement]:
        """Get movements by reference type and ID"""
        
        result = await self.db.execute(
            select(StockMovement)
            .options(selectinload(StockMovement.item), selectinload(StockMovement.location))
            .where(
                and_(
                    StockMovement.reference_type == reference_type,
                    StockMovement.reference_id == reference_id
                )
            )
            .order_by(desc(StockMovement.movement_date))
        )
        return result.scalars().all()

    async def get_movements_by_batch(self, batch_number: str) -> List[StockMovement]:
        """Get movements by batch number"""
        
        result = await self.db.execute(
            select(StockMovement)
            .options(selectinload(StockMovement.item), selectinload(StockMovement.location))
            .where(StockMovement.batch_number == batch_number)
            .order_by(desc(StockMovement.movement_date))
        )
        return result.scalars().all()

    async def get_expiring_stock_movements(
        self,
        days_until_expiry: int = 30,
        location_id: Optional[int] = None
    ) -> List[StockMovement]:
        """Get stock movements with expiring items"""
        
        expiry_threshold = datetime.utcnow().date() + timedelta(days=days_until_expiry)
        
        query = select(StockMovement).options(
            selectinload(StockMovement.item),
            selectinload(StockMovement.location)
        ).where(
            and_(
                StockMovement.expiry_date.isnot(None),
                StockMovement.expiry_date <= expiry_threshold,
                StockMovement.movement_type.in_([
                    StockMovementType.INBOUND,
                    StockMovementType.TRANSFER
                ])
            )
        )
        
        if location_id:
            query = query.where(StockMovement.location_id == location_id)
        
        query = query.order_by(StockMovement.expiry_date)
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_location_movement_stats(
        self,
        location_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get movement statistics for a specific location"""
        
        conditions = [StockMovement.location_id == location_id]
        
        if start_date:
            conditions.append(cast(StockMovement.movement_date, Date) >= start_date)
        
        if end_date:
            conditions.append(cast(StockMovement.movement_date, Date) <= end_date)
        
        # Total movements
        total_result = await self.db.execute(
            select(func.count(StockMovement.id))
            .where(and_(*conditions))
        )
        total_movements = total_result.scalar()
        
        # Inbound vs Outbound
        inbound_result = await self.db.execute(
            select(
                func.sum(StockMovement.quantity),
                func.sum(StockMovement.total_cost)
            )
            .where(
                and_(
                    *conditions,
                    StockMovement.movement_type.in_([
                        StockMovementType.INBOUND,
                        StockMovementType.TRANSFER
                    ])
                )
            )
        )
        inbound_data = inbound_result.first()
        
        outbound_result = await self.db.execute(
            select(
                func.sum(StockMovement.quantity),
                func.sum(StockMovement.total_cost)
            )
            .where(
                and_(
                    *conditions,
                    StockMovement.movement_type.in_([
                        StockMovementType.OUTBOUND,
                        StockMovementType.WASTE,
                        StockMovementType.DAMAGE,
                        StockMovementType.EXPIRED
                    ])
                )
            )
        )
        outbound_data = outbound_result.first()
        
        return {
            'total_movements': total_movements,
            'inbound': {
                'quantity': float(inbound_data[0] or 0),
                'value': float(inbound_data[1] or 0)
            },
            'outbound': {
                'quantity': float(outbound_data[0] or 0),
                'value': float(outbound_data[1] or 0)
            },
            'net_quantity': float((inbound_data[0] or 0) - (outbound_data[0] or 0)),
            'net_value': float((inbound_data[1] or 0) - (outbound_data[1] or 0))
        }

    async def _update_stock_level_for_movement(self, movement: StockMovement, current_user_id: int):
        """Update stock level based on movement type"""
        from app.services.inventory.stock_level_service import StockLevelService
        stock_service = StockLevelService(self.db)
        
        quantity_change = movement.quantity
        
        # Determine if this is an increase or decrease in stock
        if movement.movement_type in [StockMovementType.OUTBOUND, StockMovementType.WASTE, 
                                     StockMovementType.DAMAGE, StockMovementType.EXPIRED]:
            quantity_change = -quantity_change  # Negative for outbound movements
        elif movement.movement_type == StockMovementType.TRANSFER:
            # For transfers, this would be handled separately for from/to locations
            return
            
        await stock_service.adjust_stock(
            item_id=movement.item_id,
            location_id=movement.location_id,
            quantity_change=quantity_change,
            reason=f"Movement: {movement.movement_type.value}",
            current_user_id=current_user_id
        )

    async def bulk_create_movements(
        self,
        movements_data: List[StockMovementCreate],
        current_user_id: int,
        auto_update_stock: bool = True
    ) -> List[StockMovement]:
        """Create multiple stock movements in bulk"""
        
        created_movements = []
        
        for movement_data in movements_data:
            try:
                movement = await self.create_stock_movement(
                    movement_data=movement_data,
                    current_user_id=current_user_id,
                    auto_update_stock=auto_update_stock
                )
                created_movements.append(movement)
            except Exception as e:
                # Rollback and raise error if any movement fails
                await self.db.rollback()
                raise ValidationError(f"Failed to create movement for item {movement_data.item_id}: {str(e)}")
        
        return created_movements