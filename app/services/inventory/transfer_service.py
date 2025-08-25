from decimal import Decimal
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, func, desc
from app.models.inventory.transfer import Transfer
from app.models.inventory.transfer_item import TransferItem
from app.models.inventory.item import Item
from app.models.inventory.stock_level import StockLevel
from app.models.organization.location import Location
from app.schemas.inventory.stock_movement import StockMovementCreate
from app.schemas.inventory.transfer import TransferCreate, TransferItemCreate
from app.core.exceptions import NotFoundError, ValidationError
from app.models.shared.enums import TransferStatus, StockMovementType
from datetime import datetime, date

class TransferService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_transfer(self, transfer_data: TransferCreate, current_user_id: int) -> Transfer:
        # Validate locations exist and are different
        if transfer_data.from_location_id == transfer_data.to_location_id:
            raise ValidationError("From and to locations cannot be the same")

        from_location = await self.db.execute(select(Location).where(Location.id == transfer_data.from_location_id))
        if not from_location.scalar_one_or_none():
            raise ValidationError("From location not found")

        to_location = await self.db.execute(select(Location).where(Location.id == transfer_data.to_location_id))
        if not to_location.scalar_one_or_none():
            raise ValidationError("To location not found")

        # Generate transfer number
        transfer_number = await self._generate_transfer_number()

        transfer = Transfer(
            transfer_number=transfer_number,
            from_location_id=transfer_data.from_location_id,
            to_location_id=transfer_data.to_location_id,
            transfer_date=transfer_data.transfer_date or date.today(),
            expected_date=transfer_data.expected_date,
            requested_by=current_user_id,
            notes=transfer_data.notes,
            created_by=current_user_id
        )
        
        self.db.add(transfer)
        await self.db.flush()  # Get the ID

        # Add items and check stock availability
        for item_data in transfer_data.items:
            await self._add_transfer_item(transfer.id, item_data, transfer_data.from_location_id, current_user_id)

        await self.db.commit()
        await self.db.refresh(transfer)
        result = await self.db.execute(
            select(Transfer)
            .options(
                selectinload(Transfer.from_location),
                selectinload(Transfer.to_location),
                selectinload(Transfer.items).selectinload(TransferItem.item).options(
                    selectinload(Item.category),      
                    selectinload(Item.stock_levels), 
                    selectinload(Item.stock_type)  
                )
            )
            .where(Transfer.id == transfer.id)
        )
        return result.scalar_one_or_none()


    async def _generate_transfer_number(self) -> str:
        """Generate unique transfer number"""
        today = date.today()
        prefix = f"TR-{today.strftime('%Y%m%d')}"
        
        result = await self.db.execute(
            select(func.count(Transfer.id))
            .where(Transfer.transfer_number.like(f"{prefix}%"))
        )
        count = result.scalar() + 1
        
        return f"{prefix}-{count:04d}"

    async def _add_transfer_item(self, transfer_id: int, item_data: TransferItemCreate, from_location_id: int, current_user_id: int):
        """Add item to transfer and validate stock availability"""
        # Validate item exists
        item = await self.db.execute(select(Item).where(Item.id == item_data.item_id))
        if not item.scalar_one_or_none():
            raise ValidationError(f"Item {item_data.item_id} not found")

        # Check stock availability
        stock_level_result = await self.db.execute(
            select(StockLevel)
            .where(and_(
                StockLevel.item_id == item_data.item_id,
                StockLevel.location_id == from_location_id
            ))
        )
        stock_level = stock_level_result.scalar_one_or_none()
        
        if not stock_level or stock_level.available_stock < item_data.requested_quantity:
            raise ValidationError(f"Insufficient stock for item {item_data.item_id}")

        transfer_item = TransferItem(
            transfer_id=transfer_id,
            item_id=item_data.item_id,
            requested_quantity=item_data.requested_quantity,
            unit_cost=item_data.unit_cost,
            batch_number=item_data.batch_number,
            expiry_date=item_data.expiry_date,
            created_by=current_user_id
        )
        
        self.db.add(transfer_item)

    async def get_transfer_by_id(self, transfer_id: int) -> Optional[Transfer]:
        result = await self.db.execute(
            select(Transfer)
            .options(
                selectinload(Transfer.from_location),
                selectinload(Transfer.to_location),
                selectinload(Transfer.items).selectinload(TransferItem.item).options(
                    selectinload(Item.category),      
                    selectinload(Item.stock_levels),   
                )
            )
            .where(Transfer.id == transfer_id)
        )
        return result.scalar_one_or_none()

    async def get_transfers(
        self, 
        skip: int = 0, 
        limit: int = 100,
        from_location_id: Optional[int] = None,
        to_location_id: Optional[int] = None,
        status: Optional[TransferStatus] = None
    ) -> List[Transfer]:
        query = (
        select(Transfer)
            .options(
                selectinload(Transfer.from_location),
                selectinload(Transfer.to_location),
                selectinload(Transfer.items).selectinload(TransferItem.item).options(
                    selectinload(Item.category),       # preload category
                    selectinload(Item.stock_levels),   # preload stock_levels
                )
            )
            .order_by(desc(Transfer.transfer_date))
        )

        
        conditions = []
        if from_location_id:
            conditions.append(Transfer.from_location_id == from_location_id)
        if to_location_id:
            conditions.append(Transfer.to_location_id == to_location_id)
        if status:
            conditions.append(Transfer.status == status)
            
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def approve_transfer(self, transfer_id: int, current_user_id: int) -> Transfer:
        """Approve transfer and reserve stock"""
        transfer = await self.get_transfer_by_id(transfer_id)
        if not transfer:
            raise NotFoundError("Transfer not found")

        if transfer.status != TransferStatus.PENDING:
            raise ValidationError("Only pending transfers can be approved")

        # Reserve stock for all items
        from app.services.inventory.stock_level_service import StockLevelService
        stock_service = StockLevelService(self.db)

        for item in transfer.items:
            await stock_service.reserve_stock(
                item_id=item.item_id,
                location_id=transfer.from_location_id,
                quantity=item.requested_quantity,
                current_user_id=current_user_id
            )

        transfer.status = TransferStatus.IN_TRANSIT
        transfer.approved_by = current_user_id
        transfer.approved_date = datetime.utcnow()
        transfer.updated_by = current_user_id

        await self.db.commit()
        await self.db.refresh(transfer)
        return transfer

    async def send_transfer(self, transfer_id: int, sent_quantities: Dict[int, Decimal], current_user_id: int) -> Transfer:
        """Mark transfer as sent with actual sent quantities"""
        transfer = await self.get_transfer_by_id(transfer_id)
        if not transfer:
            raise NotFoundError("Transfer not found")

        if transfer.status != TransferStatus.IN_TRANSIT:
            raise ValidationError("Only approved transfers can be sent")

        # Update sent quantities and create stock movements
        from app.services.inventory.stock_movement_service import StockMovementService
        movement_service = StockMovementService(self.db)

        for item in transfer.items:
            if item.item_id in sent_quantities:
                item.sent_quantity = sent_quantities[item.item_id]
                item.updated_by = current_user_id

                # Create outbound movement from source location
                await movement_service.create_stock_movement(
                    movement_data=StockMovementCreate(**{
                        'item_id': item.item_id,
                        'location_id': transfer.from_location_id,
                        'movement_type': StockMovementType.TRANSFER,
                        'quantity': item.sent_quantity,
                        'unit_cost': item.unit_cost,
                        'reference_type': 'TRANSFER',
                        'reference_id': transfer.id,
                        'batch_number': item.batch_number,
                        'expiry_date': item.expiry_date,
                        'remarks': f"Transfer to {transfer.to_location.name}"
                    }),
                    current_user_id=current_user_id,
                    auto_update_stock=True
                )
        transfer.sent_by = current_user_id
        transfer.sent_date = datetime.utcnow()
        transfer.updated_by = current_user_id

        await self.db.commit()
        await self.db.refresh(transfer)
        return transfer

    async def receive_transfer(self, transfer_id: int, received_quantities: Dict[int, Decimal], current_user_id: int) -> Transfer:
        """Mark transfer as received with actual received quantities"""
        transfer = await self.get_transfer_by_id(transfer_id)
        if not transfer:
            raise NotFoundError("Transfer not found")

        if transfer.status != TransferStatus.IN_TRANSIT:
            raise ValidationError("Only sent transfers can be received")

        # Update received quantities and create stock movements
        from app.services.inventory.stock_movement_service import StockMovementService
        movement_service = StockMovementService(self.db)

        for item in transfer.items:
            if item.item_id in received_quantities:
                item.received_quantity = received_quantities[item.item_id]
                item.updated_by = current_user_id

                # Create inbound movement to destination location
                await movement_service.create_stock_movement(
                    movement_data=StockMovementCreate(**{
                        'item_id': item.item_id,
                        'location_id': transfer.to_location_id,
                        'movement_type': StockMovementType.INBOUND,
                        'quantity': item.received_quantity,
                        'unit_cost': item.unit_cost,
                        'reference_type': 'TRANSFER',
                        'reference_id': transfer.id,
                        'batch_number': item.batch_number,
                        'expiry_date': item.expiry_date,
                        'remarks': f"Transfer from {transfer.from_location.name}"
                    }),
                    current_user_id=current_user_id,
                    auto_update_stock=True
                )

        transfer.status = TransferStatus.COMPLETED
        transfer.received_by = current_user_id
        transfer.received_date = datetime.utcnow()
        transfer.updated_by = current_user_id

        await self.db.commit()
        await self.db.refresh(transfer)
        return transfer

    async def cancel_transfer(self, transfer_id: int, reason: str, current_user_id: int) -> Transfer:
        """Cancel transfer and release reserved stock"""
        transfer = await self.get_transfer_by_id(transfer_id)
        if not transfer:
            raise NotFoundError("Transfer not found")

        if transfer.status in [TransferStatus.COMPLETED, TransferStatus.CANCELLED]:
            raise ValidationError("Cannot cancel completed or already cancelled transfer")

        # Release reserved stock if transfer was approved
        if transfer.status == TransferStatus.IN_TRANSIT:
            from app.services.inventory.stock_level_service import StockLevelService
            stock_service = StockLevelService(self.db)

            for item in transfer.items:
                await stock_service.release_reservation(
                    item_id=item.item_id,
                    location_id=transfer.from_location_id,
                    quantity=item.requested_quantity,
                    current_user_id=current_user_id
                )

        transfer.status = TransferStatus.CANCELLED
        transfer.notes = f"{transfer.notes or ''}\n\nCancellation reason: {reason}"
        transfer.updated_by = current_user_id

        await self.db.commit()
        await self.db.refresh(transfer)
        return transfer

def transfer_none():
    return None