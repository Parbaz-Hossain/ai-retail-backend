import logging
from typing import Any, List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.schemas.common.pagination import PaginatedResponse
from app.services.purchase.purchase_order_service import PurchaseOrderService
from app.models.shared.enums import PurchaseOrderStatus
from app.schemas.purchase.purchase_order_schema import (PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderResponse)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    po_data: PurchaseOrderCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Create a new purchase order"""
    try:
        po_service = PurchaseOrderService(session)
        purchase_order = await po_service.create_purchase_order(po_data, current_user.id)
        return purchase_order
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating purchase order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create purchase order"
        )

@router.get("/", response_model=PaginatedResponse[PurchaseOrderResponse])
async def get_purchase_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[PurchaseOrderStatus] = Query(None, alias="status"),
    supplier_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Get purchase orders with pagination and filters"""
    try:
        po_service = PurchaseOrderService(session)
        result = await po_service.get_purchase_orders(
            skip=skip,
            limit=limit,
            status=status_filter,
            supplier_id=supplier_id,
            start_date=start_date,
            end_date=end_date,
            search=search
        )
        return result
    except Exception as e:
        logger.error(f"Error getting purchase orders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get purchase orders"
        )

@router.get("/{po_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    po_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get purchase order by ID"""
    try:
        po_service = PurchaseOrderService(session)
        purchase_order = await po_service.get_purchase_order(po_id)
        if not purchase_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found"
            )
        return purchase_order
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get purchase order"
        )

@router.put("/{po_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    po_id: int,
    po_data: PurchaseOrderUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update purchase order"""
    try:
        po_service = PurchaseOrderService(session)
        purchase_order = await po_service.update_purchase_order(po_id, po_data, current_user.id)
        if not purchase_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found"
            )
        return purchase_order
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update purchase order"
        )

@router.post("/{po_id}/submit")
async def submit_purchase_order(
    po_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Submit purchase order for approval"""
    try:
        po_service = PurchaseOrderService(session)
        success = await po_service.submit_for_approval(po_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to submit purchase order for approval"
            )
        return {"message": "Purchase order submitted for approval"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit purchase order"
        )

@router.post("/{po_id}/approve")
async def approve_purchase_order(
    po_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Approve purchase order"""
    try:
        po_service = PurchaseOrderService(session)
        success = await po_service.approve_purchase_order(po_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to approve purchase order"
            )
        return {"message": "Purchase order approved"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve purchase order"
        )

@router.post("/{po_id}/reject")
async def reject_purchase_order(
    po_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Reject purchase order"""
    try:
        po_service = PurchaseOrderService(session)
        success = await po_service.reject_purchase_order(po_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to reject purchase order"
            )
        return {"message": "Purchase order rejected"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject purchase order"
        )

@router.post("/{po_id}/cancel")
async def cancel_purchase_order(
    po_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Cancel purchase order"""
    try:
        po_service = PurchaseOrderService(session)
        success = await po_service.cancel_purchase_order(po_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to cancel purchase order"
            )
        return {"message": "Purchase order cancelled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel purchase order"
        )

@router.delete("/{po_id}")
async def delete_purchase_order(
    po_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Delete purchase order"""
    try:
        po_service = PurchaseOrderService(session)
        success = await po_service.delete_purchase_order(po_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found"
            )
        return {"message": "Purchase order deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete purchase order"
        )

@router.get("/{po_id}/summary", response_model=Any)
async def get_purchase_order_summary(
    po_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get purchase order summary with receiving status"""
    try:
        po_service = PurchaseOrderService(session)
        summary = await po_service.get_po_summary(po_id)
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found"
            )
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting purchase order summary {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get purchase order summary"
        )

@router.get("/{po_id}/pending-items", response_model=List[Any])
async def get_pending_items_for_receipt(
    po_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get pending items for receiving from a purchase order"""
    try:
        from app.services.purchase.goods_receipt_service import GoodsReceiptService
        receipt_service = GoodsReceiptService(session)
        pending_items = await receipt_service.get_pending_receipts_for_po(po_id)
        return pending_items
    except Exception as e:
        logger.error(f"Error getting pending items for PO {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pending items"
        )