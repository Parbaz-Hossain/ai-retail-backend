import logging
from typing import Any, List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.api.dependencies import get_current_user, require_permission
from app.schemas.common.pagination import PaginatedResponse
from app.services.purchase.purchase_order_service import PurchaseOrderService
from app.models.shared.enums import PurchaseOrderStatus
from app.schemas.purchase.purchase_order_schema import (PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderResponse, PurchaseOrderItemCreate)
from app.utils.file_handler import FileUploadService
from decimal import Decimal

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    supplier_id: int = Form(...),
    location_id: Optional[int] = Form(None),
    order_date: Optional[str] = Form(None),
    expected_delivery_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    payment_conditions: Optional[str] = Form(None),
    tax_amount: Optional[str] = Form("0"),
    discount_amount: Optional[str] = Form("0"),
    files: List[UploadFile] = File(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user),
    _permission = Depends(require_permission("purchase_order", "create"))
):
    """Create a new purchase order with master data only"""
    try:
        # Parse dates
        parsed_order_date = None
        if order_date:
            parsed_order_date = date.fromisoformat(order_date)
        
        parsed_expected_delivery_date = None
        if expected_delivery_date:
            parsed_expected_delivery_date = date.fromisoformat(expected_delivery_date)

        # Create PO data
        po_data = PurchaseOrderCreate(
            supplier_id=supplier_id,
            location_id=location_id,
            order_date=parsed_order_date,
            expected_delivery_date=parsed_expected_delivery_date,
            notes=notes,
            payment_conditions=payment_conditions,
            tax_amount=Decimal(tax_amount or "0"),
            discount_amount=Decimal(discount_amount or "0")
        )

        po_service = PurchaseOrderService(session)
        purchase_order = await po_service.create_purchase_order(po_data, current_user.id)
        
        # Handle multiple file uploads if provided
        if files and any(file.filename for file in files if file):
            file_service = FileUploadService()
            file_paths = []
            
            for file in files:
                if file and file.filename:
                    try:
                        file_path = await file_service.save_file(file, "purchase_orders", purchase_order.id)
                        file_paths.append(file_path)
                    except Exception as e:
                        logger.error(f"Error uploading file {file.filename}: {str(e)}")
                        # Continue with other files even if one fails
                        continue
            
            if file_paths:
                # Update PO with file paths
                await po_service.update_po_file_paths(purchase_order.id, file_paths)
                purchase_order.file_paths = file_paths

        return purchase_order
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating purchase order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create purchase order"
        )

@router.put("/{po_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    po_id: int,
    supplier_id: Optional[int] = Form(None),
    location_id: Optional[int] = Form(None),
    expected_delivery_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    payment_conditions: Optional[str] = Form(None),
    tax_amount: Optional[str] = Form(None),
    discount_amount: Optional[str] = Form(None),
    files: List[UploadFile] = File(None),
    replace_files: bool = Form(False),  # If True, replace all existing files; if False, append to existing
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user),
    _permission = Depends(require_permission("purchase_order", "update"))
):
    """Update purchase order"""
    try:
        # Parse dates
        parsed_expected_delivery_date = None
        if expected_delivery_date:
            parsed_expected_delivery_date = date.fromisoformat(expected_delivery_date)

        # Create update data
        update_data = {}
        if supplier_id is not None:
            update_data['supplier_id'] = supplier_id
        if location_id is not None:
            update_data['location_id'] = location_id
        if parsed_expected_delivery_date is not None:
            update_data['expected_delivery_date'] = parsed_expected_delivery_date
        if notes is not None:
            update_data['notes'] = notes
        if payment_conditions is not None:
            update_data['payment_conditions'] = payment_conditions
        if tax_amount is not None:
            update_data['tax_amount'] = Decimal(tax_amount)
        if discount_amount is not None:
            update_data['discount_amount'] = Decimal(discount_amount)

        po_data = PurchaseOrderUpdate(**update_data)
        po_service = PurchaseOrderService(session)
        purchase_order = await po_service.update_purchase_order(po_id, po_data, current_user.id)
        
        if not purchase_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase order not found"
            )

        # Handle multiple file uploads if provided
        if files and any(file.filename for file in files if file):
            file_service = FileUploadService()
            new_file_paths = []
            
            for file in files:
                if file and file.filename:
                    try:
                        file_path = await file_service.save_file(file, "purchase_orders", po_id)
                        new_file_paths.append(file_path)
                    except Exception as e:
                        logger.error(f"Error uploading file {file.filename}: {str(e)}")
                        # Continue with other files even if one fails
                        continue
            
            if new_file_paths:
                # Get existing file paths if not replacing
                existing_file_paths = []
                if not replace_files and purchase_order.file_paths:
                    existing_file_paths = purchase_order.file_paths
                
                # Combine existing and new file paths
                all_file_paths = existing_file_paths + new_file_paths
                
                # Update PO with file paths
                await po_service.update_po_file_paths(po_id, all_file_paths)
                purchase_order.file_paths = all_file_paths

        return purchase_order
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update purchase order"
        )

@router.delete("/{po_id}/files/{file_index}")
async def delete_file_from_purchase_order(
    po_id: int,
    file_index: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Delete a specific file from purchase order by index"""
    try:
        po_service = PurchaseOrderService(session)
        success = await po_service.delete_po_file(po_id, file_index)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete file from purchase order"
            )
        return {"message": "File deleted from purchase order successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file from purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file from purchase order"
        )

@router.post("/{po_id}/items", response_model=dict)
async def add_item_to_purchase_order(
    po_id: int,
    item_data: PurchaseOrderItemCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user),
    _permission = Depends(require_permission("purchase_order", "create"))
):
    """Add item to existing purchase order"""
    try:
        po_service = PurchaseOrderService(session)
        success = await po_service.add_item_to_po(po_id, item_data, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to add item to purchase order"
            )
        return {"message": "Item added to purchase order successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding item to purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add item to purchase order"
        )

@router.delete("/{po_id}/items/{item_id}")
async def remove_item_from_purchase_order(
    po_id: int,
    item_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user),
    _permission = Depends(require_permission("purchase_order", "delete"))
):
    """Remove item from purchase order"""
    try:
        po_service = PurchaseOrderService(session)
        success = await po_service.remove_item_from_po(po_id, item_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove item from purchase order"
            )
        return {"message": "Item removed from purchase order successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing item from purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove item from purchase order"
        )

# Keep all existing endpoints as they are
@router.get("/", response_model=PaginatedResponse[PurchaseOrderResponse])
async def get_purchase_orders(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    status_filter: Optional[PurchaseOrderStatus] = Query(None, alias="status"),
    supplier_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get purchase orders with pagination and filters"""
    try:
        po_service = PurchaseOrderService(session)
        result = await po_service.get_purchase_orders(
            page_index=page_index,
            page_size=page_size,
            status=status_filter,
            supplier_id=supplier_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
            user_id=current_user.id
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
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
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
    current_user = Depends(get_current_user),
    _permission = Depends(require_permission("purchase_order", "approve"))
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
    current_user = Depends(get_current_user),
    _permission = Depends(require_permission("purchase_order", "reject"))
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
    current_user = Depends(get_current_user),
    _permission = Depends(require_permission("purchase_order", "cancel"))
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
    current_user = Depends(get_current_user),
    _permission = Depends(require_permission("purchase_order", "delete"))
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
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
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