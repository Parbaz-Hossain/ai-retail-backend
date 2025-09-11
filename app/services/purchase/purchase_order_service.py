# app/services/purchase/purchase_order_service.py
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.purchase.purchase_order import PurchaseOrder
from app.models.purchase.purchase_order_item import PurchaseOrderItem
from app.models.purchase.supplier import Supplier
from app.models.inventory.item import Item
from app.models.shared.enums import PurchaseOrderStatus
from app.schemas.purchase.purchase_order_schema import (
    PurchaseOrderCreate,
    PurchaseOrderResponse, 
    PurchaseOrderUpdate, 
    PurchaseOrderItemCreate
)
from app.services.task.task_integration_service import TaskIntegrationService

logger = logging.getLogger(__name__)

class PurchaseOrderService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_po_number(self) -> str:
        """Generate unique purchase order number"""
        try:
            today = date.today()
            prefix = f"PO{today.strftime('%Y%m%d')}"
            
            # Get the latest PO number for today
            result = await self.session.execute(
                select(func.max(PurchaseOrder.po_number))
                .where(PurchaseOrder.po_number.like(f"{prefix}%"))
            )
            latest_po = result.scalar()
            
            if latest_po:
                # Extract sequence number and increment
                sequence = int(latest_po[-3:]) + 1
            else:
                sequence = 1
                
            return f"{prefix}{sequence:03d}"
            
        except Exception as e:
            logger.error(f"Error generating PO number: {str(e)}")
            # Fallback to timestamp-based number
            return f"PO{datetime.now().strftime('%Y%m%d%H%M%S')}"

    async def create_purchase_order(
        self, 
        po_data: PurchaseOrderCreate, 
        user_id: int
    ) -> PurchaseOrder:
        """Create new purchase order with optional auto-approval task"""
        try:
            # Verify supplier exists
            supplier_result = await self.session.execute(
                select(Supplier).where(
                    and_(
                        Supplier.id == po_data.supplier_id,
                        Supplier.is_active == True,
                        Supplier.is_deleted == False
                    )
                )
            )
            supplier = supplier_result.scalar_one_or_none()
            if not supplier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Supplier not found or inactive"
                )

            # Generate PO number
            po_number = await self.generate_po_number()

            # Calculate totals
            subtotal = sum(
                Decimal(str(item.quantity)) * Decimal(str(item.unit_cost))
                for item in po_data.items
            )
            tax_amount = po_data.tax_amount or Decimal('0')
            discount_amount = po_data.discount_amount or Decimal('0')
            total_amount = subtotal + tax_amount - discount_amount

            # Create purchase order
            purchase_order = PurchaseOrder(
                po_number=po_number,
                supplier_id=po_data.supplier_id,
                order_date=po_data.order_date or date.today(),
                expected_delivery_date=po_data.expected_delivery_date,
                status=PurchaseOrderStatus.DRAFT,
                subtotal=subtotal,
                tax_amount=tax_amount,
                discount_amount=discount_amount,
                total_amount=total_amount,
                notes=po_data.notes,
                requested_by=user_id,
                created_by = user_id
            )

            self.session.add(purchase_order)
            await self.session.flush()  # Get the ID

            # Create PO items
            po_items = []
            for item_data in po_data.items:
                # Verify item exists
                item_result = await self.session.execute(
                    select(Item).where(Item.id == item_data.item_id)
                )
                if not item_result.scalar_one_or_none():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Item {item_data.item_id} not found"
                    )

                total_cost = Decimal(str(item_data.quantity)) * Decimal(str(item_data.unit_cost))
                
                po_item = PurchaseOrderItem(
                    purchase_order_id=purchase_order.id,
                    item_id=item_data.item_id,
                    quantity=item_data.quantity,
                    unit_cost=item_data.unit_cost,
                    total_cost=total_cost,
                    received_quantity=Decimal('0'),
                    created_by=user_id
                )
                po_items.append(po_item)

            self.session.add_all(po_items)
            await self.session.commit()

            # Auto-submit for approval if requested
            await self._submit_for_approval(purchase_order.id, user_id)

            # Reload PO with items eagerly
            result = await self.session.execute(
                select(PurchaseOrder)
                .options(selectinload(PurchaseOrder.supplier))
                .options(selectinload(PurchaseOrder.items))
                .where(PurchaseOrder.id == purchase_order.id)
            )
            purchase_order = result.scalar_one()
            logger.info(f"Purchase order created: {purchase_order.po_number} by user {user_id}")
            return PurchaseOrderResponse.model_validate(purchase_order, from_attributes=True)

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating purchase order: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create purchase order"
            )

    async def get_purchase_order(self, po_id: int) -> Optional[PurchaseOrder]:
        """Get purchase order by ID with only non-deleted items"""
        try:
            result = await self.session.execute(
                select(PurchaseOrder)
                .options(
                    selectinload(PurchaseOrder.items.and_(PurchaseOrderItem.is_deleted == False)).selectinload(PurchaseOrderItem.item),
                    selectinload(PurchaseOrder.supplier)
                )
                .where(
                    and_(
                        PurchaseOrder.id == po_id,
                        PurchaseOrder.is_deleted == False
                    )
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting purchase order {po_id}: {str(e)}")
            return None

    async def get_purchase_orders(
        self,
        page_index: int = 1,
        page_size: int = 100,
        status: Optional[PurchaseOrderStatus] = None,
        supplier_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get purchase orders with pagination and filters"""
        try:
            # Base query
            query = select(PurchaseOrder).options(
                selectinload(PurchaseOrder.supplier),
                selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.item)
            ).where(PurchaseOrder.is_deleted == False)

            # Apply filters
            if status:
                query = query.where(PurchaseOrder.status == status)
            
            if supplier_id:
                query = query.where(PurchaseOrder.supplier_id == supplier_id)
            
            if start_date:
                query = query.where(PurchaseOrder.order_date >= start_date)
                
            if end_date:
                query = query.where(PurchaseOrder.order_date <= end_date)
            
            if search:
                search_filter = or_(
                    PurchaseOrder.po_number.ilike(f"%{search}%"),
                    PurchaseOrder.notes.ilike(f"%{search}%")
                )
                query = query.where(search_filter)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total = total_result.scalar() or 0

            # Calculate offset and apply pagination
            skip = (page_index - 1) * page_size
            query = query.offset(skip).limit(page_size).order_by(PurchaseOrder.order_date.desc())
            result = await self.session.execute(query)
            purchase_orders = result.scalars().all()

            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": purchase_orders
            }

        except Exception as e:
            logger.error(f"Error getting purchase orders: {str(e)}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def update_purchase_order(
        self,
        po_id: int,
        po_data: PurchaseOrderUpdate,
        user_id: int
    ) -> Optional[PurchaseOrder]:
        """Update purchase order"""
        try:
            po = await self.get_purchase_order(po_id)
            if not po:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Purchase order not found"
                )

            # Check if PO can be updated
            if po.status not in [PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.PENDING]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot update purchase order in current status"
                )

            # Update basic fields
            update_data = po_data.model_dump(exclude_unset=True, exclude={'items'})
            update_data['updated_by'] = user_id
            for field, value in update_data.items():
                setattr(po, field, value)

            # Update items if provided
            if po_data.items:
                # Remove existing items
                await self.session.execute(
                    update(PurchaseOrderItem)
                    .where(PurchaseOrderItem.purchase_order_id == po_id)
                    .values(is_deleted=True)
                )

                # Add new items
                subtotal = Decimal('0')
                for item_data in po_data.items:
                    total_cost = Decimal(str(item_data.quantity)) * Decimal(str(item_data.unit_cost))
                    subtotal += total_cost
                    
                    po_item = PurchaseOrderItem(
                        purchase_order_id=po_id,
                        item_id=item_data.item_id,
                        quantity=item_data.quantity,
                        unit_cost=item_data.unit_cost,
                        total_cost=total_cost,
                        received_quantity=Decimal('0'),
                        updated_by=user_id
                    )
                    self.session.add(po_item)

                # Recalculate totals
                po.subtotal = subtotal
                po.total_amount = subtotal + (po.tax_amount or Decimal('0')) - (po.discount_amount or Decimal('0'))

            await self.session.commit()
            await self.session.refresh(po)

            logger.info(f"Purchase order updated: {po_id} by user {user_id}")
            return po

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating purchase order {po_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update purchase order"
            )

    async def submit_for_approval(self, po_id: int, user_id: int) -> bool:
        """Submit purchase order for approval"""
        try:
            po = await self.get_purchase_order(po_id)
            if not po:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Purchase order not found"
                )

            if po.status != PurchaseOrderStatus.DRAFT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only draft purchase orders can be submitted for approval"
                )

            po.status = PurchaseOrderStatus.PENDING
            await self.session.commit()

            logger.info(f"Purchase order submitted for approval: {po_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error submitting purchase order for approval: {str(e)}")
            return False

    async def approve_purchase_order(self, po_id: int, user_id: int) -> bool:
        """Approve purchase order"""
        try:
            po = await self.get_purchase_order(po_id)
            if not po:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Purchase order not found"
                )

            if po.status != PurchaseOrderStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only pending purchase orders can be approved"
                )

            po.status = PurchaseOrderStatus.APPROVED
            po.approved_by = user_id
            po.approved_date = datetime.utcnow()
            
            await self.session.commit()

            logger.info(f"Purchase order approved: {po_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error approving purchase order: {str(e)}")
            return False

    async def reject_purchase_order(self, po_id: int, user_id: int) -> bool:
        """Reject purchase order"""
        try:
            po = await self.get_purchase_order(po_id)
            if not po:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Purchase order not found"
                )

            if po.status != PurchaseOrderStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only pending purchase orders can be rejected"
                )

            po.status = PurchaseOrderStatus.REJECTED
            await self.session.commit()

            logger.info(f"Purchase order rejected: {po_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error rejecting purchase order: {str(e)}")
            return False

    async def cancel_purchase_order(self, po_id: int, user_id: int) -> bool:
        """Cancel purchase order"""
        try:
            po = await self.get_purchase_order(po_id)
            if not po:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Purchase order not found"
                )

            if po.status in [PurchaseOrderStatus.COMPLETED, PurchaseOrderStatus.CANCELLED]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot cancel completed or already cancelled purchase order"
                )

            po.status = PurchaseOrderStatus.CANCELLED
            await self.session.commit()

            logger.info(f"Purchase order cancelled: {po_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error cancelling purchase order: {str(e)}")
            return False

    async def delete_purchase_order(self, po_id: int, user_id: int) -> bool:
        """Soft delete purchase order"""
        try:
            po = await self.get_purchase_order(po_id)
            if not po:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Purchase order not found"
                )

            if po.status not in [PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.REJECTED]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only draft or rejected purchase orders can be deleted"
                )

            po.is_deleted = True
            await self.session.commit()

            logger.info(f"Purchase order deleted: {po_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting purchase order: {str(e)}")
            return False

    async def get_po_summary(self, po_id: int) -> Dict[str, Any]:
        """Get purchase order summary with receiving status"""
        try:
            po = await self.get_purchase_order(po_id)
            if not po:
                return {}

            # Calculate received quantities
            total_items = len(po.items)
            fully_received_items = sum(
                1 for item in po.items 
                if item.received_quantity >= item.quantity
            )
            partially_received_items = sum(
                1 for item in po.items 
                if Decimal('0') < item.received_quantity < item.quantity
            )

            total_quantity = sum(item.quantity for item in po.items)
            total_received = sum(item.received_quantity for item in po.items)

            receiving_status = "Not Started"
            if total_received == total_quantity:
                receiving_status = "Completed"
            elif total_received > Decimal('0'):
                receiving_status = "Partial"

            return {
                "po_number": po.po_number,
                "supplier_name": po.supplier.name,
                "order_date": po.order_date,
                "status": po.status.value,
                "total_amount": float(po.total_amount),
                "total_items": total_items,
                "fully_received_items": fully_received_items,
                "partially_received_items": partially_received_items,
                "receiving_status": receiving_status,
                "total_quantity": float(total_quantity),
                "total_received": float(total_received),
                "completion_percentage": float((total_received / total_quantity * 100)) if total_quantity > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error getting PO summary: {str(e)}")
            return {}
        
    async def _submit_for_approval(self, po_id: int, user_id: int) -> bool:
        """Submit purchase order for approval and create approval task"""
        try:
            po = await self.get_purchase_order(po_id)
            if not po:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Purchase order not found"
                )

            if po.status != PurchaseOrderStatus.DRAFT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only draft purchase orders can be submitted for approval"
                )

            po.status = PurchaseOrderStatus.PENDING
            
            # CREATE APPROVAL TASK
            task_integration = TaskIntegrationService(self.session)
            await task_integration.create_purchase_approval_task(po, user_id)
            
            await self.session.commit()

            logger.info(f"Purchase order submitted for approval: {po_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error submitting purchase order for approval: {str(e)}")
            return False