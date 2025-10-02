from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, func
from app.models.inventory.inventory_mismatch_reason import InventoryMismatchReason
from app.schemas.inventory.inventory_mismatch_reason import (
    InventoryMismatchReasonCreate, 
    InventoryMismatchReasonUpdate
)
from app.core.exceptions import NotFoundError, ValidationError

class InventoryMismatchReasonService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_reason(
        self, 
        reason_data: InventoryMismatchReasonCreate, 
        current_user_id: int
    ) -> InventoryMismatchReason:
        """Create new mismatch reason"""

        reason = InventoryMismatchReason(
            **reason_data.dict(),
            created_by=current_user_id
        )
        
        self.db.add(reason)
        await self.db.commit()
        await self.db.refresh(reason)
        return reason

    async def get_reason_by_id(self, reason_id: int) -> Optional[InventoryMismatchReason]:
        """Get reason by ID"""
        result = await self.db.execute(
            select(InventoryMismatchReason).where(
                and_(
                    InventoryMismatchReason.id == reason_id,
                    InventoryMismatchReason.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_all_reasons(
        self,
        page_index: int = 1,
        page_size: int = 100,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get all reasons with pagination"""
        query = select(InventoryMismatchReason).where(
            InventoryMismatchReason.is_active == True
        )
        if search:
            query = query.where(InventoryMismatchReason.name.ilike(f"%{search}%"))
        query = query.order_by(InventoryMismatchReason.name)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Pagination
        offset = (page_index - 1) * page_size
        paginated_query = query.offset(offset).limit(page_size)
        result = await self.db.execute(paginated_query)
        reasons = result.scalars().all()

        return {
            "page_index": page_index,
            "page_size": page_size,
            "count": total,
            "data": reasons
        }

    async def update_reason(
        self, 
        reason_id: int, 
        reason_data: InventoryMismatchReasonUpdate, 
        current_user_id: int
    ) -> InventoryMismatchReason:
        """Update mismatch reason"""
        reason = await self.get_reason_by_id(reason_id)
        if not reason:
            raise NotFoundError("Reason not found")

        for field, value in reason_data.dict(exclude_unset=True).items():
            setattr(reason, field, value)
        
        reason.updated_by = current_user_id
        await self.db.commit()
        await self.db.refresh(reason)
        return reason

    async def delete_reason(self, reason_id: int, current_user_id: int) -> bool:
        """delete reason"""
        reason = await self.get_reason_by_id(reason_id)
        if not reason:
            raise NotFoundError("Reason not found")

        # Check if reason is in use
        from app.models.inventory.inventory_count_item import InventoryCountItem
        usage_result = await self.db.execute(
            select(InventoryCountItem).where(
                InventoryCountItem.reason_id == reason_id
            ).limit(1)
        )
        if usage_result.scalar_one_or_none():
            raise ValidationError("Cannot delete reason that is in use")

        await self.db.delete(reason)
        await self.db.commit()
        return True