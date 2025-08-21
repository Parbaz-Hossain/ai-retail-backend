import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.models.purchase.supplier import Supplier
from app.models.purchase.item_supplier import ItemSupplier
from app.models.inventory.item import Item
from app.schemas.purchase.supplier_schema import SupplierCreate, SupplierUpdate

logger = logging.getLogger(__name__)

class SupplierService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_supplier(self, supplier_data: SupplierCreate, user_id: int) -> Supplier:
        """Create a new supplier"""
        try:
            # Check if supplier code already exists
            existing = await self.session.execute(
                select(Supplier).where(
                    and_(
                        Supplier.supplier_code == supplier_data.supplier_code,
                        Supplier.is_deleted == False
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Supplier code already exists"
                )

            # Create new supplier
            supplier = Supplier(**supplier_data.model_dump())
            self.session.add(supplier)
            await self.session.commit()
            await self.session.refresh(supplier)

            logger.info(f"Supplier created: {supplier.id} by user {user_id}")
            return supplier

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating supplier: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create supplier"
            )

    async def get_supplier(self, supplier_id: int) -> Optional[Supplier]:
        """Get supplier by ID"""
        try:
            result = await self.session.execute(
                select(Supplier)
                .options(selectinload(Supplier.item_suppliers))
                .where(
                    and_(
                        Supplier.id == supplier_id,
                        Supplier.is_deleted == False
                    )
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting supplier {supplier_id}: {str(e)}")
            return None

    async def get_suppliers(
        self,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get suppliers with pagination and filters"""
        try:
            # Base query
            query = select(Supplier).where(Supplier.is_deleted == False)

            # Apply filters
            if search:
                search_filter = or_(
                    Supplier.name.ilike(f"%{search}%"),
                    Supplier.supplier_code.ilike(f"%{search}%"),
                    Supplier.contact_person.ilike(f"%{search}%")
                )
                query = query.where(search_filter)

            if is_active is not None:
                query = query.where(Supplier.is_active == is_active)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total = total_result.scalar()

            # Apply pagination and execute
            query = query.offset(skip).limit(limit).order_by(Supplier.name)
            result = await self.session.execute(query)
            suppliers = result.scalars().all()

            return {
                "items": suppliers,
                "total": total,
                "skip": skip,
                "limit": limit
            }

        except Exception as e:
            logger.error(f"Error getting suppliers: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get suppliers"
            )

    async def update_supplier(
        self, 
        supplier_id: int, 
        supplier_data: SupplierUpdate, 
        user_id: int
    ) -> Optional[Supplier]:
        """Update supplier"""
        try:
            supplier = await self.get_supplier(supplier_id)
            if not supplier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Supplier not found"
                )

            # Check if new supplier code conflicts
            if supplier_data.supplier_code and supplier_data.supplier_code != supplier.supplier_code:
                existing = await self.session.execute(
                    select(Supplier).where(
                        and_(
                            Supplier.supplier_code == supplier_data.supplier_code,
                            Supplier.id != supplier_id,
                            Supplier.is_deleted == False
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Supplier code already exists"
                    )

            # Update supplier
            for field, value in supplier_data.model_dump(exclude_unset=True).items():
                setattr(supplier, field, value)

            await self.session.commit()
            await self.session.refresh(supplier)

            logger.info(f"Supplier updated: {supplier_id} by user {user_id}")
            return supplier

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating supplier {supplier_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update supplier"
            )

    async def delete_supplier(self, supplier_id: int, user_id: int) -> bool:
        """Soft delete supplier"""
        try:
            supplier = await self.get_supplier(supplier_id)
            if not supplier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Supplier not found"
                )

            # Check if supplier has active purchase orders
            from app.models.purchase.purchase_order import PurchaseOrder
            from app.models.shared.enums import PurchaseOrderStatus
            
            active_po_result = await self.session.execute(
                select(PurchaseOrder).where(
                    and_(
                        PurchaseOrder.supplier_id == supplier_id,
                        PurchaseOrder.status.in_([
                            PurchaseOrderStatus.DRAFT,
                            PurchaseOrderStatus.PENDING,
                            PurchaseOrderStatus.APPROVED
                        ])
                    )
                )
            )
            if active_po_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete supplier with active purchase orders"
                )

            supplier.is_deleted = True
            await self.session.commit()

            logger.info(f"Supplier deleted: {supplier_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting supplier {supplier_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete supplier"
            )

    async def add_item_to_supplier(
        self,
        supplier_id: int,
        item_id: int,
        supplier_item_code: Optional[str],
        unit_cost: float,
        minimum_order_quantity: float = 1,
        lead_time_days: int = 0,
        is_preferred: bool = False,
        user_id: int = None
    ) -> ItemSupplier:
        """Add item to supplier"""
        try:
            # Verify supplier exists
            supplier = await self.get_supplier(supplier_id)
            if not supplier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Supplier not found"
                )

            # Verify item exists
            item_result = await self.session.execute(
                select(Item).where(Item.id == item_id)
            )
            item = item_result.scalar_one_or_none()
            if not item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Item not found"
                )

            # Check if relationship already exists
            existing = await self.session.execute(
                select(ItemSupplier).where(
                    and_(
                        ItemSupplier.item_id == item_id,
                        ItemSupplier.supplier_id == supplier_id,
                        ItemSupplier.is_deleted == False
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Item already exists for this supplier"
                )

            # Create item-supplier relationship
            item_supplier = ItemSupplier(
                item_id=item_id,
                supplier_id=supplier_id,
                supplier_item_code=supplier_item_code,
                unit_cost=unit_cost,
                minimum_order_quantity=minimum_order_quantity,
                lead_time_days=lead_time_days,
                is_preferred=is_preferred
            )

            self.session.add(item_supplier)
            await self.session.commit()
            await self.session.refresh(item_supplier)

            logger.info(f"Item {item_id} added to supplier {supplier_id} by user {user_id}")
            return item_supplier

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error adding item to supplier: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add item to supplier"
            )

    async def remove_item_from_supplier(
        self, 
        supplier_id: int, 
        item_id: int, 
        user_id: int
    ) -> bool:
        """Remove item from supplier"""
        try:
            result = await self.session.execute(
                select(ItemSupplier).where(
                    and_(
                        ItemSupplier.supplier_id == supplier_id,
                        ItemSupplier.item_id == item_id,
                        ItemSupplier.is_deleted == False
                    )
                )
            )
            item_supplier = result.scalar_one_or_none()

            if not item_supplier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Item-supplier relationship not found"
                )

            item_supplier.is_deleted = True
            await self.session.commit()

            logger.info(f"Item {item_id} removed from supplier {supplier_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error removing item from supplier: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove item from supplier"
            )

    async def get_supplier_items(self, supplier_id: int) -> List[ItemSupplier]:
        """Get all items for a supplier"""
        try:
            result = await self.session.execute(
                select(ItemSupplier)
                .options(selectinload(ItemSupplier.item))
                .where(
                    and_(
                        ItemSupplier.supplier_id == supplier_id,
                        ItemSupplier.is_deleted == False
                    )
                )
                .order_by(ItemSupplier.is_preferred.desc(), ItemSupplier.unit_cost)
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting supplier items: {str(e)}")
            return []

    async def get_preferred_suppliers_for_item(self, item_id: int) -> List[ItemSupplier]:
        """Get preferred suppliers for an item"""
        try:
            result = await self.session.execute(
                select(ItemSupplier)
                .options(selectinload(ItemSupplier.supplier))
                .where(
                    and_(
                        ItemSupplier.item_id == item_id,
                        ItemSupplier.is_preferred == True,
                        ItemSupplier.is_deleted == False
                    )
                )
                .join(Supplier)
                .where(Supplier.is_active == True)
                .order_by(ItemSupplier.unit_cost)
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting preferred suppliers for item {item_id}: {str(e)}")
            return []