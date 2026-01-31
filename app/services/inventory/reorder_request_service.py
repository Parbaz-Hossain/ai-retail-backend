from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, func, desc, update
from datetime import datetime, date
from decimal import Decimal

from app.models.inventory.reorder_request import ReorderRequest
from app.models.inventory.reorder_request_item import ReorderRequestItem
from app.models.inventory.item import Item
from app.models.inventory.stock_level import StockLevel
from app.models.organization.location import Location
from app.schemas.inventory.reorder_request import ReorderRequestCreate, ReorderRequestUpdate, ReorderRequestItemCreate
from app.core.exceptions import NotFoundError, ValidationError
from app.models.shared.enums import ReorderRequestStatus
from app.services.auth.user_service import UserService
from app.services.task.task_integration_service import TaskIntegrationService

class ReorderRequestService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    async def create_reorder_request(self, request_data: ReorderRequestCreate, current_user_id: int) -> ReorderRequest:
        # Validate location exists
        location = await self.db.execute(select(Location).where(Location.id == request_data.location_id))
        if not location.scalar_one_or_none():
            raise ValidationError("Location not found")

        # Generate request number
        request_number = await self._generate_request_number()

        reorder_request = ReorderRequest(
            request_number=request_number,
            location_id=request_data.location_id,
            request_date=request_data.request_date or date.today(),
            required_date=request_data.required_date,
            total_estimated_cost=0,
            requested_by=current_user_id,
            notes=request_data.notes,
            to_location_id=request_data.to_location_id,
            created_by=current_user_id
        )
        
        self.db.add(reorder_request)
        await self.db.commit()
        await self.db.refresh(reorder_request)

        # Reload with relationships
        result = await self.db.execute(
            select(ReorderRequest)
            .options(
                selectinload(ReorderRequest.location),
                selectinload(ReorderRequest.to_location),
                selectinload(ReorderRequest.items)
                    .selectinload(ReorderRequestItem.item)
                    .options(
                        selectinload(Item.category),
                        selectinload(Item.stock_levels),
                        selectinload(Item.stock_type) 
                    )
            )
            .where(ReorderRequest.id == reorder_request.id)
        )

        reorder_request = result.scalars().unique().one()
        
        # CREATE APPROVAL TASK
        task_integration = TaskIntegrationService(self.db)
        await task_integration.create_reorder_approval_task(reorder_request)
        
        return reorder_request

    async def _generate_request_number(self) -> str:
        """Generate unique request number"""
        today = date.today()
        prefix = f"RR-{today.strftime('%Y%m%d')}"
        
        # Get last number for today
        result = await self.db.execute(
            select(func.count(ReorderRequest.id))
            .where(ReorderRequest.request_number.like(f"{prefix}%"))
        )
        count = result.scalar() + 1
        
        return f"{prefix}-{count:04d}"

    async def add_item_to_reorder_request(self, request_id: int, item_data: ReorderRequestItemCreate, current_user_id: int) -> bool:
        """Add item to existing reorder request"""
        reorder_request = await self.get_reorder_request_by_id(request_id)
        if not reorder_request:
            raise NotFoundError("Reorder request not found")

        if reorder_request.status not in [ReorderRequestStatus.PENDING]:
            raise ValidationError("Cannot add items to reorder request in current status")

        # Validate item exists
        item = await self.db.execute(select(Item).where(Item.id == item_data.item_id))
        if not item.scalar_one_or_none():
            raise ValidationError(f"Item {item_data.item_id} not found")

        # Check if item already exists
        existing_item = await self.db.execute(
            select(ReorderRequestItem).where(
                and_(
                    ReorderRequestItem.reorder_request_id == request_id,
                    ReorderRequestItem.item_id == item_data.item_id,
                    ReorderRequestItem.is_deleted == False
                )
            )
        )
        if existing_item.scalar_one_or_none():
            raise ValidationError("Item already exists in reorder request")

        # Get current stock level from the requesting location
        current_stock = Decimal(0)
        stock_level_result = await self.db.execute(
            select(StockLevel.current_stock)
            .where(and_(
                StockLevel.item_id == item_data.item_id,
                StockLevel.location_id == reorder_request.location_id
            ))
        )
        stock_level = stock_level_result.scalar_one_or_none()
        if stock_level:
            current_stock = stock_level

        reorder_item = ReorderRequestItem(
            reorder_request_id=request_id,
            item_id=item_data.item_id,
            unit_type=item_data.unit_type,
            current_stock=current_stock,
            requested_quantity=item_data.requested_quantity,
            reason=item_data.reason,
            created_by=current_user_id
        )
        
        self.db.add(reorder_item)
        await self.db.commit()
        return True

    async def remove_item_from_reorder_request(self, request_id: int, item_id: int, current_user_id: int) -> bool:
        """Remove item from reorder request"""
        reorder_request = await self.get_reorder_request_by_id(request_id)
        if not reorder_request:
            raise NotFoundError("Reorder request not found")

        if reorder_request.status not in [ReorderRequestStatus.PENDING]:
            raise ValidationError("Cannot remove items from reorder request in current status")

        await self.db.execute(
            ReorderRequestItem.__table__.delete().where(
            and_(
                ReorderRequestItem.reorder_request_id == request_id,
                ReorderRequestItem.id == item_id
            )
            )
        )

        await self.db.commit()
        return True

    async def get_reorder_request_by_id(self, request_id: int) -> Optional[ReorderRequest]:
        result = await self.db.execute(
            select(ReorderRequest)
            .options(
                 selectinload(ReorderRequest.location),
                 selectinload(ReorderRequest.to_location),
                 selectinload(ReorderRequest.items)
                    .selectinload(ReorderRequestItem.item)
                    .options(
                        selectinload(Item.category),
                        selectinload(Item.stock_levels),
                        selectinload(Item.stock_type) 
                    )
            )
            .where(ReorderRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_reorder_requests(
        self, 
        page_index: int = 1,
        page_size: int = 100,
        location_id: Optional[int] = None,
        status: Optional[ReorderRequestStatus] = None,
        priority: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get reorder requests with pagination"""
        try:
            query = select(ReorderRequest).options(
                selectinload(ReorderRequest.location),
                selectinload(ReorderRequest.to_location),
                selectinload(ReorderRequest.items)
                    .selectinload(ReorderRequestItem.item)
                    .options(
                        selectinload(Item.category),
                        selectinload(Item.stock_levels),
                        selectinload(Item.stock_type) 
                    )
            ).order_by(desc(ReorderRequest.request_date))
            
            conditions = []
            if location_id:
                conditions.append(ReorderRequest.location_id == location_id)
            if status:
                conditions.append(ReorderRequest.status == status)
            if priority:
                conditions.append(ReorderRequest.priority == priority)
                
            # Location manager restriction
            if user_id:
                role_name = await self.user_service.get_specific_role_name_by_user(user_id, "location_manager")
                if role_name:
                    loc_res = await self.db.execute(
                        select(Location.id).where(Location.manager_id == user_id)
                    )
                    loc_ids = loc_res.scalars().all()
                    if loc_ids:
                        conditions.append(ReorderRequest.location_id.in_(loc_ids))
            
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
            requests = result.scalars().all()
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": requests
            }
        except Exception as e:
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def update_reorder_request(self, request_id: int, request_data: ReorderRequestUpdate, current_user_id: int) -> ReorderRequest:
        reorder_request = await self.get_reorder_request_by_id(request_id)
        if not reorder_request:
            raise NotFoundError("Reorder request not found")

        # Check if request can be updated (not approved/completed)
        if reorder_request.status in [ReorderRequestStatus.COMPLETED]:
            raise ValidationError("Cannot update completed request")

        for field, value in request_data.dict(exclude_unset=True).items():
            setattr(reorder_request, field, value)
        
        reorder_request.updated_by = current_user_id
        await self.db.commit()
        await self.db.refresh(reorder_request)
        return reorder_request

    async def approve_reorder_request(self, request_id: int, approved_quantities: Dict[int, Decimal], current_user_id: int) -> ReorderRequest:
        """Approve reorder request with specific quantities for each item"""
        reorder_request = await self.get_reorder_request_by_id(request_id)
        if not reorder_request:
            raise NotFoundError("Reorder request not found")

        if reorder_request.status != ReorderRequestStatus.PENDING:
            raise ValidationError("Only pending requests can be approved")

        # Update item approved quantities
        for item in reorder_request.items:
            if item.item_id in approved_quantities:
                item.approved_quantity = approved_quantities[item.item_id]
                item.updated_by = current_user_id

        reorder_request.status = ReorderRequestStatus.APPROVED
        reorder_request.approved_by = current_user_id
        reorder_request.approved_date = datetime.utcnow()
        reorder_request.updated_by = current_user_id

        await self.db.commit()
        await self.db.refresh(reorder_request)
        return reorder_request

    async def reject_reorder_request(self, request_id: int, reason: str, current_user_id: int) -> ReorderRequest:
        """Reject reorder request"""
        reorder_request = await self.get_reorder_request_by_id(request_id)
        if not reorder_request:
            raise NotFoundError("Reorder request not found")

        if reorder_request.status != ReorderRequestStatus.PENDING:
            raise ValidationError("Only pending requests can be rejected")

        reorder_request.status = ReorderRequestStatus.REJECTED
        reorder_request.notes = f"{reorder_request.notes or ''}\n\nRejection reason: {reason}"
        reorder_request.updated_by = current_user_id

        await self.db.commit()
        await self.db.refresh(reorder_request)
        return reorder_request

    async def auto_generate_reorder_requests(self, user_id: int, location_id: Optional[int] = None) -> List[ReorderRequest]:
        """Auto-generate reorder requests for items below reorder point"""
        # Get items below reorder point
        query = select(Item, StockLevel).join(StockLevel).where(
            and_(
                Item.is_active == True,
                StockLevel.current_stock <= Item.reorder_point,
                Item.reorder_point > 0  # Only items with reorder point set
            )
        )
        
        if location_id:
            query = query.where(StockLevel.location_id == location_id)
            
        result = await self.db.execute(query)
        low_stock_items = result.all()

        if not low_stock_items:
            return []

        # Group by location
        items_by_location = {}
        for item, stock_level in low_stock_items:
            loc_id = stock_level.location_id
            if loc_id not in items_by_location:
                items_by_location[loc_id] = []
            
            # Calculate suggested quantity (reorder to max level or 2x reorder point)
            suggested_qty = max(
                item.maximum_stock_level - stock_level.current_stock,
                item.reorder_point * 2 - stock_level.current_stock
            ) if item.maximum_stock_level else item.reorder_point * 2 - stock_level.current_stock
            
            items_by_location[loc_id].append({
                'item': item,
                'stock_level': stock_level,
                'suggested_quantity': suggested_qty
            })

        # Create reorder requests for each location
        created_requests = []
        task_integration = TaskIntegrationService(self.db)
        for loc_id, items in items_by_location.items():
            request_items = []
            for item_data in items:
                request_items.append(ReorderRequestItemCreate(
                    item_id=item_data['item'].id,
                    requested_quantity=item_data['suggested_quantity'],
                    estimated_unit_cost=item_data['item'].unit_cost,
                    reason="Auto-generated: Below reorder point"
                ))

            request_data = ReorderRequestCreate(
                location_id=loc_id,
                priority="HIGH",
                notes="Auto-generated reorder request for low stock items",
                items=request_items
            )

            request = await self.create_reorder_request(request_data, current_user_id=user_id)  # System user
             # Create high-priority task for auto-generated requests
            await task_integration.create_reorder_approval_task(request)
            created_requests.append(request)

        return created_requests