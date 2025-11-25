import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.organization.location import Location
from app.models.purchase.goods_receipt import GoodsReceipt
from app.models.purchase.goods_receipt_item import GoodsReceiptItem
from app.models.purchase.purchase_order import PurchaseOrder
from app.models.purchase.purchase_order_item import PurchaseOrderItem
from app.models.inventory.stock_level import StockLevel
from app.models.inventory.stock_movement import StockMovement
from app.models.shared.enums import PurchaseOrderStatus, StockMovementType
from app.schemas.purchase.goods_receipt_schema import (
    GoodsReceiptCreate,
    GoodsReceiptItemCreate,
    GoodsReceiptResponse,
    GoodsReceiptUpdate
)
from app.services.auth.user_service import UserService
from app.services.task.task_service import TaskService
from app.models.shared.enums import TaskStatus, ReferenceType

logger = logging.getLogger(__name__)

class GoodsReceiptService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(session)

    async def generate_receipt_number(self) -> str:
        """Generate unique goods receipt number"""
        try:
            today = date.today()
            prefix = f"GR{today.strftime('%Y%m%d')}"
            
            # Get the latest receipt number for today
            result = await self.session.execute(
                select(func.max(GoodsReceipt.receipt_number))
                .where(GoodsReceipt.receipt_number.like(f"{prefix}%"))
            )
            latest_receipt = result.scalar()
            
            if latest_receipt:
                sequence = int(latest_receipt[-3:]) + 1
            else:
                sequence = 1
                
            return f"{prefix}{sequence:03d}"
            
        except Exception as e:
            logger.error(f"Error generating receipt number: {str(e)}")
            return f"GR{datetime.now().strftime('%Y%m%d%H%M%S')}"

    async def create_goods_receipt(
        self,
        receipt_data: GoodsReceiptCreate,
        user_id: int
    ) -> GoodsReceipt:
        """Create new goods receipt"""
        try:
            # Verify purchase order exists and is approved
            po_result = await self.session.execute(
                select(PurchaseOrder)
                .options(
                    selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.item),
                    selectinload(PurchaseOrder.supplier)
                )
                .where(
                    and_(
                        PurchaseOrder.id == receipt_data.purchase_order_id,
                        PurchaseOrder.is_deleted == False
                    )
                )
            )
            purchase_order = po_result.scalar_one_or_none()
            
            if not purchase_order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Purchase order not found"
                )

            if purchase_order.status not in [PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.PARTIALLY_RECEIVED]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Can only receive items from approved or partially received purchase orders"
                )

            # Generate receipt number
            receipt_number = await self.generate_receipt_number()

            # Create goods receipt
            goods_receipt = GoodsReceipt(
                receipt_number=receipt_number,
                purchase_order_id=receipt_data.purchase_order_id,
                supplier_id=purchase_order.supplier_id,
                receipt_date=receipt_data.receipt_date or date.today(),
                location_id=receipt_data.location_id,
                received_by=user_id,
                notes=receipt_data.notes,
                created_by=user_id
            )

            self.session.add(goods_receipt)
            await self.session.flush()  # Get the ID

            # Process receipt items
            receipt_items = []
            for item_data in receipt_data.items:
                # Find the corresponding PO item
                po_item = next(
                    (poi for poi in purchase_order.items if poi.id == item_data.purchase_order_item_id),
                    None
                )
                
                if not po_item:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Purchase order item {item_data.purchase_order_item_id} not found"
                    )

                # Validate received quantity doesn't exceed remaining quantity
                remaining_qty = po_item.quantity - po_item.received_quantity
                if item_data.received_quantity > remaining_qty:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Received quantity ({item_data.received_quantity}) exceeds remaining quantity ({remaining_qty}) for item {po_item.item.name}"
                    )

                # Create receipt item
                receipt_item = GoodsReceiptItem(
                    goods_receipt_id=goods_receipt.id,
                    purchase_order_item_id=item_data.purchase_order_item_id,
                    item_id=po_item.item_id,
                    ordered_quantity=po_item.quantity,
                    received_quantity=item_data.received_quantity,
                    unit_cost=po_item.unit_cost,
                    batch_number=item_data.batch_number,
                    expiry_date=item_data.expiry_date,
                    created_by=user_id
                )
                receipt_items.append(receipt_item)

                # Update PO item received quantity
                po_item.received_quantity += item_data.received_quantity

                # Update stock levels
                await self._update_stock_levels(
                    item_id=po_item.item_id,
                    location_id=receipt_data.location_id,
                    quantity=item_data.received_quantity,
                    unit_cost=po_item.unit_cost,
                    user_id=user_id,
                    reference_id=goods_receipt.id,
                    batch_number=item_data.batch_number,
                    expiry_date=item_data.expiry_date
                )

            self.session.add_all(receipt_items)

            # Check if PO is fully received
            await self._check_po_completion(purchase_order.id)

            await self.session.commit()

            # COMPLETE PURCHASE ORDER APPROVAL TASK
            await self._complete_po_approval_task(purchase_order.id, user_id)
            
            # CHECK AND UPDATE LOW STOCK TASKS
            for receipt_item in receipt_items:
                await self._check_and_complete_low_stock_task(
                    receipt_item.item_id,
                    receipt_data.location_id,
                    user_id
                )

             # Reload PO with items eagerly
            result = await self.session.execute(
                select(GoodsReceipt)
                .options(
                    selectinload(GoodsReceipt.supplier),
                    selectinload(GoodsReceipt.purchase_order),
                    selectinload(GoodsReceipt.location),
                    selectinload(GoodsReceipt.items).selectinload(GoodsReceiptItem.item)
                )
                .where(GoodsReceipt.id == goods_receipt.id)
            )

            logger.info(f"Goods receipt created: {receipt_number} by user {user_id}")
            goods_receipt = result.scalar_one()
            return GoodsReceiptResponse.model_validate(goods_receipt, from_attributes=True)

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating goods receipt: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create goods receipt"
            )

    async def get_goods_receipt(self, receipt_id: int) -> Optional[GoodsReceipt]:
        """Get goods receipt by ID"""
        try:
            result = await self.session.execute(
                select(GoodsReceipt)
                .options(
                    selectinload(GoodsReceipt.supplier),
                    selectinload(GoodsReceipt.purchase_order),
                    selectinload(GoodsReceipt.location),
                    selectinload(GoodsReceipt.items).selectinload(GoodsReceiptItem.item)
                )
                .where(
                    and_(
                        GoodsReceipt.id == receipt_id,
                        GoodsReceipt.is_deleted == False
                    )
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting goods receipt {receipt_id}: {str(e)}")
            return None

    async def get_goods_receipts(
        self,
        page_index: int = 1,
        page_size: int = 100,
        supplier_id: Optional[int] = None,
        purchase_order_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        search: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get goods receipts with pagination and filters"""
        try:
            # Base query
            query = (select(GoodsReceipt)
            .options(
                selectinload(GoodsReceipt.supplier),
                selectinload(GoodsReceipt.purchase_order),
                selectinload(GoodsReceipt.location),
                selectinload(GoodsReceipt.items).selectinload(GoodsReceiptItem.item)
            )).where(GoodsReceipt.is_deleted == False)

            # Apply filters
            if supplier_id:
                query = query.where(GoodsReceipt.supplier_id == supplier_id)
            
            if purchase_order_id:
                query = query.where(GoodsReceipt.purchase_order_id == purchase_order_id)
            
            if start_date:
                query = query.where(GoodsReceipt.receipt_date >= start_date)
                
            if end_date:
                query = query.where(GoodsReceipt.receipt_date <= end_date)
            
            if search:
                search_filter = or_(
                    GoodsReceipt.receipt_number.ilike(f"%{search}%"),
                    GoodsReceipt.location.name.ilike(f"%{search}%"),
                    GoodsReceipt.notes.ilike(f"%{search}%")
                )
                query = query.where(search_filter)

            # Location manager restriction - handles multiple locations per manager
            if user_id:
                role_name = await self.user_service.get_specific_role_name_by_user(user_id, "location_manager")
                if role_name:
                    loc_res = await self.session.execute(
                        select(Location.id).where(Location.manager_id == user_id)
                    )
                    loc_ids = loc_res.scalars().all()
                    if loc_ids:
                        query = query.where(GoodsReceipt.location_id.in_(loc_ids))

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total = total_result.scalar() or 0

            # Calculate offset and apply pagination
            skip = (page_index - 1) * page_size
            query = query.offset(skip).limit(page_size).order_by(GoodsReceipt.receipt_date.desc())
            result = await self.session.execute(query)
            receipts = result.scalars().all()

            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": receipts
            }

        except Exception as e:
            logger.error(f"Error getting goods receipts: {str(e)}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }
        
    async def update_goods_receipt(
        self,
        receipt_id: int,
        receipt_data: GoodsReceiptUpdate,
        user_id: int
    ) -> Optional[GoodsReceipt]:
        """Update goods receipt (limited fields only)"""
        try:
            receipt = await self.get_goods_receipt(receipt_id)
            if not receipt:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Goods receipt not found"
                )

            # Update allowed fields
            update_data = receipt_data.model_dump(exclude_unset=True)
            update_data["updated_by"] = user_id
            for field, value in update_data.items():
                if field in ['notes', 'updated_by']:  # Only allow these fields to be updated
                    setattr(receipt, field, value)

            await self.session.commit()
            await self.session.refresh(receipt)

            logger.info(f"Goods receipt updated: {receipt_id} by user {user_id}")
            return receipt

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating goods receipt {receipt_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update goods receipt"
            )

    async def delete_goods_receipt(self, receipt_id: int, user_id: int) -> bool:
        """Delete goods receipt (reverse stock movements)"""
        try:
            receipt = await self.get_goods_receipt(receipt_id)
            if not receipt:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Goods receipt not found"
                )

            # Reverse stock movements for all items
            for receipt_item in receipt.items:
                # Reverse stock level update
                await self._reverse_stock_levels(
                    item_id=receipt_item.item_id,
                    location_id=receipt.location_id,
                    quantity=receipt_item.received_quantity,
                    user_id=user_id,
                    reference_id=receipt.id
                )

                # Update PO item received quantity
                po_item_result = await self.session.execute(
                    select(PurchaseOrderItem).where(
                        PurchaseOrderItem.id == receipt_item.purchase_order_item_id
                    )
                )
                po_item = po_item_result.scalar_one_or_none()
                if po_item:
                    po_item.received_quantity -= receipt_item.received_quantity

            # Soft delete the receipt
            receipt.is_deleted = True
            
            # Check PO status again
            await self._check_po_completion(receipt.purchase_order.id)
            
            await self.session.commit()

            logger.info(f"Goods receipt deleted: {receipt_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting goods receipt: {str(e)}")
            return False

    async def _update_stock_levels(
        self,
        item_id: int,
        location_id: int,
        quantity: Decimal,
        unit_cost: Decimal,
        user_id: int,
        reference_id: int,
        batch_number: Optional[str] = None,
        expiry_date: Optional[date] = None
    ):
        """Update stock levels and create stock movement"""
        try:
            # Get or create stock level
            stock_result = await self.session.execute(
                select(StockLevel).where(
                    and_(
                        StockLevel.item_id == item_id,
                        StockLevel.location_id == location_id,
                        StockLevel.is_deleted == False
                    )
                )
            )
            stock_level = stock_result.scalar_one_or_none()

            if not stock_level:
                # Create new stock level
                stock_level = StockLevel(
                    item_id=item_id,
                    location_id=location_id,
                    current_stock=quantity,
                    available_stock=quantity,
                    reserved_stock=Decimal('0'),
                    par_level_min=Decimal('0'),
                    par_level_max=Decimal('0'),
                    updated_by=user_id
                )
                self.session.add(stock_level)
            else:
                # Update existing stock level
                stock_level.current_stock += quantity
                stock_level.available_stock += quantity
                # Update unit cost with weighted average
                # total_value = (stock_level.current_stock - quantity) * stock_level.unit_cost + quantity * unit_cost
                # stock_level.unit_cost = total_value / stock_level.current_stock if stock_level.current_stock > 0 else unit_cost

            # Create stock movement record
            stock_movement = StockMovement(
                item_id=item_id,
                location_id=location_id,
                movement_type=StockMovementType.INBOUND,
                quantity=quantity,
                unit_cost=unit_cost,
                reference_type='goods_receipt',
                reference_id=reference_id,
                batch_number=batch_number,
                expiry_date=expiry_date,
                remarks=f"Goods receipt - {batch_number}" if batch_number else "Goods receipt",
                updated_by=user_id
            )
            self.session.add(stock_movement)

        except Exception as e:
            logger.error(f"Error updating stock levels: {str(e)}")
            raise

    async def _reverse_stock_levels(
        self,
        item_id: int,
        location_id: int,
        quantity: Decimal,
        user_id: int,
        reference_id: int
    ):
        """Reverse stock level changes"""
        try:
            # Get stock level
            stock_result = await self.session.execute(
                select(StockLevel).where(
                    and_(
                        StockLevel.item_id == item_id,
                        StockLevel.location_id == location_id,
                        StockLevel.is_deleted == False
                    )
                )
            )
            stock_level = stock_result.scalar_one_or_none()

            if stock_level:
                # Check if we have enough stock to reverse
                if stock_level.current_stock < quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Insufficient stock to reverse receipt. Current: {stock_level.current_stock}, Required: {quantity}"
                    )

                # Update stock level
                stock_level.current_stock -= quantity
                stock_level.available_stock -= quantity

                # Create reverse stock movement
                stock_movement = StockMovement(
                    item_id=item_id,
                    location_id=location_id,
                    movement_type=StockMovementType.ADJUSTMENT,
                    quantity=-quantity,  # Negative quantity for reversal
                    reference_type='goods_receipt_reversal',
                    reference_id=reference_id,
                    remarks="Goods receipt reversal",
                    created_by=user_id
                )
                self.session.add(stock_movement)

        except Exception as e:
            logger.error(f"Error reversing stock levels: {str(e)}")
            raise

    async def _check_po_completion(self, purchase_order_id: int):
        """Check if purchase order is fully received"""
        try:
            # Explicitly load the purchase order with its items
            po_result = await self.session.execute(
                select(PurchaseOrder)
                .options(selectinload(PurchaseOrder.items))
                .where(PurchaseOrder.id == purchase_order_id)
            )
            purchase_order = po_result.scalar_one_or_none()
            
            if not purchase_order:
                logger.warning(f"Purchase order {purchase_order_id} not found")
                return
        
            # Check if all items are fully received
            all_received = all(
                item.received_quantity >= item.quantity
                for item in purchase_order.items
            )

            # Check if any items are partially received
            any_received = any(
                item.received_quantity > Decimal('0')
                for item in purchase_order.items
            )

            if all_received:
                purchase_order.status = PurchaseOrderStatus.COMPLETED
            elif any_received:
                purchase_order.status = PurchaseOrderStatus.PARTIALLY_RECEIVED

        except Exception as e:
            logger.error(f"Error checking PO completion: {str(e)}")

    async def get_pending_receipts_for_po(self, po_id: int) -> List[Dict[str, Any]]:
        """Get pending items for receiving from a purchase order"""
        try:
            po_result = await self.session.execute(
                select(PurchaseOrder)
                .options(selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.item))
                .where(
                    and_(
                        PurchaseOrder.id == po_id,
                        PurchaseOrder.is_deleted == False,
                        PurchaseOrderItem.is_deleted == False
                    )
                )
            )
            po = po_result.scalar_one_or_none()

            if not po:
                return []

            pending_items = []
            for po_item in po.items:
                remaining_qty = po_item.quantity - po_item.received_quantity
                if remaining_qty > 0:
                    pending_items.append({
                        "purchase_order_item_id": po_item.id,
                        "item_id": po_item.item_id,
                        "item_name": po_item.item.name,
                        "ordered_quantity": float(po_item.quantity),
                        "received_quantity": float(po_item.received_quantity),
                        "remaining_quantity": float(remaining_qty),
                        "unit_cost": float(po_item.unit_cost),
                        "unit": po_item.item.unit_type.value if po_item.item.unit_type else None
                    })

            return pending_items

        except Exception as e:
            logger.error(f"Error getting pending receipts for PO {po_id}: {str(e)}")
            return []
        
    async def _complete_po_approval_task(self, po_id: int, user_id: int):
        """Complete purchase order approval task"""
        try:
            from app.models.task.task import Task
            
            # Find related task
            result = await self.session.execute(
                select(Task).where(
                    and_(
                        Task.reference_type == ReferenceType.PURCHASE_ORDER.value,
                        Task.reference_id == po_id,
                        Task.status != TaskStatus.COMPLETED,
                        Task.is_active == True
                    )
                )
            )
            task = result.scalar_one_or_none()
            
            if task:
                task_service = TaskService(self.session)
                await task_service.update_task_status(
                    task_id=task.id,
                    status=TaskStatus.COMPLETED,
                    user_id=user_id,
                    notes="Purchase order received and processed"
                )
                
        except Exception as e:
            logger.error(f"Failed to complete PO task: {str(e)}")
    
    async def _check_and_complete_low_stock_task(
        self, 
        item_id: int, 
        location_id: int,
        user_id: int
    ):
        """Check and complete low stock tasks after receiving goods"""
        try:
            from app.models.task.task import Task
            from app.models.inventory.stock_level import StockLevel
            from app.models.inventory.item import Item
            
            # Check current stock level
            stock_result = await self.session.execute(
                select(StockLevel, Item)
                .join(Item)
                .where(
                    and_(
                        StockLevel.item_id == item_id,
                        StockLevel.location_id == location_id
                    )
                )
            )
            result = stock_result.first()
            
            if result:
                stock_level, item = result
                
                # If stock is now above reorder point
                if stock_level.current_stock > item.reorder_point:
                    # Find and complete related low stock task
                    task_result = await self.session.execute(
                        select(Task).where(
                            and_(
                                Task.reference_type == ReferenceType.LOW_STOCK_ALERT.value,
                                Task.reference_id == item_id,
                                Task.location_id == location_id,
                                Task.status != TaskStatus.COMPLETED,
                                Task.is_active == True
                            )
                        )
                    )
                    task = task_result.scalar_one_or_none()
                    
                    if task:
                        task_service = TaskService(self.session)
                        await task_service.update_task_status(
                            task_id=task.id,
                            status=TaskStatus.COMPLETED,
                            user_id=user_id,
                            notes=f"Stock replenished. Current: {stock_level.current_stock}"
                        )
                        
        except Exception as e:
            logger.error(f"Failed to complete low stock task: {str(e)}")
    