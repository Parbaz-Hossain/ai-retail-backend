import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, and_, func, update
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.purchase.po_payment import POPayment, PaymentStatus, PaymentType
from app.models.purchase.purchase_order import PurchaseOrder
from app.schemas.purchase.po_payment_schema import POPaymentCreate, POPaymentResponse, POPaymentUpdate

logger = logging.getLogger(__name__)

class POPaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_payment(
        self, 
        payment_data: POPaymentCreate, 
        user_id: int,
        file_paths: Optional[List[str]] = None
    ) -> POPayment:
        """Create new PO payment"""
        try:
            # Get PO and validate
            po = await self._get_purchase_order(payment_data.purchase_order_id)
            if not po:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Purchase order not found"
                )

            # Validate PO status - only approved POs can have payments
            if po.status.value != "APPROVED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only approved purchase orders can have payments"
                )

            # Check if PO is closed
            if po.is_closed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot create payment for closed purchase order"
                )

            # Validate payment amount doesn't exceed remaining amount
            paid_amount = po.paid_amount if po.paid_amount is not None else Decimal('0')
            remaining_amount = po.total_amount - paid_amount
            if payment_data.payment_amount > remaining_amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Payment amount {payment_data.payment_amount} exceeds remaining amount {remaining_amount}"
                )

            # Validate user can only create payments for their own POs
            if po.requested_by != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only create payments for your own purchase orders"
                )

            # Create payment
            payment = POPayment(
                purchase_order_id=payment_data.purchase_order_id,
                payment_amount=payment_data.payment_amount,
                payment_type=payment_data.payment_type,
                status=PaymentStatus.PENDING,
                notes=payment_data.notes,
                file_paths=file_paths,
                requested_by=user_id,
                created_by=user_id
            )

            self.session.add(payment)
            await self.session.commit()

            logger.info(f"PO payment created: {payment.id} for PO {payment_data.purchase_order_id}")
            return payment

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating PO payment: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create payment"
            )

    async def approve_payment(self, payment_id: int, user_id: int) -> bool:
        """Approve PO payment and update PO paid percentage"""
        try:
            # Get payment
            payment = await self._get_payment(payment_id)
            if not payment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )

            if payment.status != PaymentStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only pending payments can be approved"
                )

            # Approve payment
            payment.status = PaymentStatus.APPROVED
            payment.approved_by = user_id
            payment.approved_date = datetime.utcnow()

            # Update PO paid amount and percentage
            await self._update_po_payment_status(payment.purchase_order_id)
            
            await self.session.commit()

            logger.info(f"Payment approved: {payment_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error approving payment: {str(e)}")
            return False

    async def reject_payment(self, payment_id: int, user_id: int) -> bool:
        """Reject PO payment and reverse PO paid amount/percentage to enable new payment"""
        try:
            payment = await self._get_payment(payment_id)
            if not payment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )

            # Allow rejection of payments in any status except already rejected
            if payment.status == PaymentStatus.REJECTED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Payment is already rejected"
                )

            # Mark payment as rejected
            payment.status = PaymentStatus.REJECTED
            payment.approved_by = user_id
            payment.approved_date = datetime.utcnow()

            # Update PO paid amount and percentage BEFORE committing
            await self._update_po_payment_status(payment.purchase_order_id)
            
            await self.session.commit()

            logger.info(f"Payment rejected: {payment_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error rejecting payment: {str(e)}")
            return False
    
    async def close_purchase_order(self, po_id: int, user_id: int) -> bool:
        """Close PO and create final payment with remaining amount"""
        try:
            po = await self._get_purchase_order(po_id)
            if not po:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Purchase order not found"
                )

            if po.is_closed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Purchase order is already closed"
                )

            remaining_amount = po.total_amount - po.paid_amount

            # Create close payment if there's remaining amount
            if remaining_amount > 0:
                close_payment = POPayment(
                    purchase_order_id=po_id,
                    payment_amount=remaining_amount,
                    payment_type=PaymentType.CLOSE,
                    status=PaymentStatus.APPROVED,  # Auto-approved
                    notes="Auto-generated close payment",
                    requested_by=po.requested_by,
                    approved_by=user_id,
                    approved_date=datetime.utcnow(),
                    created_by=user_id
                )
                self.session.add(close_payment)

            # Close PO and update payment status
            po.is_closed = True
            await self._update_po_payment_status(po_id)

            await self.session.commit()

            logger.info(f"Purchase order closed: {po_id} by user {user_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error closing purchase order: {str(e)}")
            return False

    async def get_all_po_payments(
        self, 
        page_index: int = 1,
        page_size: int = 100,
        purchase_order_id: Optional[int] = None,
        status: Optional[PaymentStatus] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get all payments with pagination and filters"""
        try:
            filters = [POPayment.is_deleted == False]
            
            if purchase_order_id is not None:
                filters.append(POPayment.purchase_order_id == purchase_order_id)
            
            if status is not None:
                filters.append(POPayment.status == status)
            
            if search:
                filters.append(
                    or_(
                        POPayment.notes.ilike(f"%{search}%"),
                        PurchaseOrder.po_number.ilike(f"%{search}%")
                    )
                )

            query = (
                select(POPayment)
                .options(selectinload(POPayment.purchase_order))
                .join(PurchaseOrder, POPayment.purchase_order_id == PurchaseOrder.id)
                .where(and_(*filters))
                .order_by(POPayment.created_at.desc())
            )

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total = total_result.scalar() or 0

            # Pagination
            skip = (page_index - 1) * page_size
            paginated_query = query.offset(skip).limit(page_size)
            result = await self.session.execute(paginated_query)
            payments = result.scalars().all()

            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": payments
            }

        except Exception as e:
            logger.error(f"Error getting all payments: {str(e)}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def get_po_payments(
        self, 
        page_index: int = 1,
        page_size: int = 100,
        po_id: Optional[int] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get all payments for a purchase order with pagination and optional search"""
        try:
            filters = [POPayment.is_deleted == False]
            if po_id is not None:
                filters.append(POPayment.purchase_order_id == po_id)
            if search:
                filters.append(POPayment.notes.ilike(f"%{search}%"))

            query = (select(POPayment)
                        .options(selectinload(POPayment.purchase_order))
                    .where(and_(*filters)).order_by(POPayment.created_at.desc())
                    )

            # Get total count
            count_query = select(func.count()).select_from(
                select(POPayment).where(and_(*filters)).subquery()
            )
            total_result = await self.session.execute(count_query)
            total = total_result.scalar() or 0

            # Pagination
            skip = (page_index - 1) * page_size
            paginated_query = query.offset(skip).limit(page_size)
            result = await self.session.execute(paginated_query)
            payments = result.scalars().all()

            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": payments
            }

        except Exception as e:
            logger.error(f"Error getting PO payments: {str(e)}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def get_payment(self, payment_id: int) -> Optional[POPayment]:
        """Get payment by ID"""
        return await self._get_payment(payment_id)

    async def update_payment(
        self, 
        payment_id: int, 
        payment_data: POPaymentUpdate, 
        user_id: int
    ) -> Optional[POPayment]:
        """Update payment (only if pending)"""
        try:
            payment = await self._get_payment(payment_id)
            if not payment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )

            if payment.status != PaymentStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only pending payments can be updated"
                )

            # Validate new amount if provided
            if payment_data.payment_amount:
                po = await self._get_purchase_order(payment.purchase_order_id)
                remaining_amount = po.total_amount - po.paid_amount
                if payment_data.payment_amount > remaining_amount:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Payment amount exceeds remaining amount {remaining_amount}"
                    )

            # Update fields
            update_data = payment_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(payment, field, value)

            payment.updated_by = user_id
            await self.session.commit()
            await self.session.refresh(payment)

            logger.info(f"Payment updated: {payment_id} by user {user_id}")
            return payment

        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating payment: {str(e)}")
            return None

    async def update_payment_files(self, payment_id: int, file_paths: List[str]) -> bool:
        """Update payment file paths"""
        try:
            await self.session.execute(
                update(POPayment)
                .where(POPayment.id == payment_id)
                .values(file_paths=file_paths)
            )
            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating payment files: {str(e)}")
            return False

    async def _get_purchase_order(self, po_id: int) -> Optional[PurchaseOrder]:
        """Get purchase order by ID"""
        try:
            result = await self.session.execute(
                select(PurchaseOrder)
                .where(
                    and_(
                        PurchaseOrder.id == po_id,
                        PurchaseOrder.is_deleted == False
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception:
            return None

    async def _get_payment(self, payment_id: int) -> Optional[POPayment]:
        """Get payment by ID"""
        try:
            result = await self.session.execute(
                select(POPayment)
                .options(selectinload(POPayment.purchase_order))
                .where(
                    and_(
                        POPayment.id == payment_id,
                        POPayment.is_deleted == False
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception:
            return None

    async def _update_po_payment_status(self, po_id: int):
        """Update PO paid amount and percentage based on approved payments"""
        try:
            # Get PO first to ensure it exists
            po = await self._get_purchase_order(po_id)
            if not po:
                logger.error(f"Purchase order not found: {po_id}")
                return

            # Get all approved payments for this PO
            result = await self.session.execute(
                select(func.coalesce(func.sum(POPayment.payment_amount), 0))
                .where(
                    and_(
                        POPayment.purchase_order_id == po_id,
                        POPayment.status == PaymentStatus.APPROVED,
                        POPayment.is_deleted == False
                    )
                )
            )
            paid_amount = result.scalar() or Decimal('0')

            # Calculate paid percentage
            paid_percentage = Decimal('0')
            if po.total_amount and po.total_amount > 0:
                paid_percentage = (paid_amount / po.total_amount * 100)
                paid_percentage = paid_percentage.quantize(Decimal('0.01'))

            # Update PO with recalculated values
            await self.session.execute(
                update(PurchaseOrder)
                .where(PurchaseOrder.id == po_id)
                .values(
                    paid_amount=paid_amount,
                    paid_percentage=paid_percentage
                )
            )

            logger.info(f"PO payment status updated: PO {po_id}, Paid: {paid_amount}, Percentage: {paid_percentage}%")

        except Exception as e:
            logger.error(f"Error updating PO payment status for PO {po_id}: {str(e)}")
            raise