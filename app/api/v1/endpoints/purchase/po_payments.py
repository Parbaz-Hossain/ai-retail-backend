import logging
from typing import List, Optional
from decimal import Decimal
from app.models.shared.enums import PaymentStatus
from app.schemas.common.pagination import PaginatedResponse
from fastapi import APIRouter, Depends, HTTPException, Query, status, Form, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.api.dependencies import get_current_user, require_permission
from app.services.purchase.po_payment_service import POPaymentService
from app.schemas.purchase.po_payment_schema import (
    POPaymentCreate, 
    POPaymentResponse, 
    POPaymentUpdate
)
from app.utils.file_handler import FileUploadService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=POPaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_po_payment(
    purchase_order_id: int = Form(...),
    location_id: Optional[int] = Form(None),
    payment_amount: str = Form(...),
    notes: str = Form(None),
    files: List[UploadFile] = File(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user),
    _permission = Depends(require_permission("po_payment", "create"))
):
    """Create new PO payment"""
    try:
        # Create payment data
        payment_data = POPaymentCreate(
            purchase_order_id=purchase_order_id,
            location_id=location_id,
            payment_amount=Decimal(payment_amount),
            notes=notes
        )

        payment_service = POPaymentService(session)
        
        # Handle file uploads if provided
        file_paths = []
        if files and any(file.filename for file in files if file):
            file_service = FileUploadService()
            
            for file in files:
                if file and file.filename:
                    try:
                        file_path = await file_service.save_file(file, "po_payments", purchase_order_id)
                        file_paths.append(file_path)
                    except Exception as e:
                        logger.error(f"Error uploading file {file.filename}: {str(e)}")
                        continue

        payment = await payment_service.create_payment(payment_data, current_user.id, file_paths)
        
        # Update file paths if uploaded
        if file_paths:
            await payment_service.update_payment_files(payment.id, file_paths)
            payment.file_paths = file_paths

        return payment

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating PO payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create PO payment"
        )
    
@router.get("/", response_model=PaginatedResponse[POPaymentResponse])
async def get_all_po_payments(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    purchase_order_id: Optional[int] = Query(None),
    status: Optional[PaymentStatus] = Query(None),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get all PO payments with pagination and filters"""
    try:
        payment_service = POPaymentService(session)
        payments = await payment_service.get_all_po_payments(
            page_index=page_index,
            page_size=page_size,
            purchase_order_id=purchase_order_id,
            status=status,
            search=search,
            user_id=current_user.id
        )
        return payments

    except Exception as e:
        logger.error(f"Error getting all PO payments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get PO payments"
        )

@router.get("/po/{po_id}", response_model=PaginatedResponse[POPaymentResponse])
async def get_po_payments(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    po_id: int = None,
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get all payments for a purchase order"""
    try:
        payment_service = POPaymentService(session)
        payments = await payment_service.get_po_payments(
            page_index=page_index,
            page_size=page_size,
            po_id=po_id,
            search=search
        )
        return payments

    except Exception as e:
        logger.error(f"Error getting PO payments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get PO payments"
        )

@router.get("/{payment_id}", response_model=POPaymentResponse)
async def get_po_payment(
    payment_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get payment by ID"""
    try:
        payment_service = POPaymentService(session)
        payment = await payment_service.get_payment(payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        return payment

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payment {payment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get payment"
        )

# region Update Payment - Disabled for now
# @router.put("/{payment_id}", response_model=POPaymentResponse)
# async def update_po_payment(
#     payment_id: int,
#     payment_amount: str = Form(None),
#     notes: str = Form(None),
#     files: List[UploadFile] = File(None),
#     replace_files: bool = Form(False),
#     session: AsyncSession = Depends(get_async_session),
#     current_user = Depends(get_current_user)
# ):
#     """Update PO payment (only if pending)"""
#     try:
#         # Create update data
#         update_data = {}
#         if payment_amount is not None:
#             update_data['payment_amount'] = Decimal(payment_amount)
#         if notes is not None:
#             update_data['notes'] = notes

#         payment_update = POPaymentUpdate(**update_data)
#         payment_service = POPaymentService(session)
        
#         payment = await payment_service.update_payment(payment_id, payment_update, current_user.id)
#         if not payment:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Payment not found or cannot be updated"
#             )

#         # Handle file uploads if provided
#         if files and any(file.filename for file in files if file):
#             file_service = FileUploadService()
#             new_file_paths = []
            
#             for file in files:
#                 if file and file.filename:
#                     try:
#                         file_path = await file_service.save_file(file, "po_payments", payment.purchase_order_id)
#                         new_file_paths.append(file_path)
#                     except Exception as e:
#                         logger.error(f"Error uploading file {file.filename}: {str(e)}")
#                         continue
            
#             if new_file_paths:
#                 # Get existing file paths if not replacing
#                 existing_file_paths = []
#                 if not replace_files and payment.file_paths:
#                     existing_file_paths = payment.file_paths
                
#                 # Combine existing and new file paths
#                 all_file_paths = existing_file_paths + new_file_paths
                
#                 # Update payment with file paths
#                 await payment_service.update_payment_files(payment_id, all_file_paths)
#                 payment.file_paths = all_file_paths

#         return payment

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error updating payment {payment_id}: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to update payment"
#         )
# endregion

@router.post("/{payment_id}/approve")
async def approve_po_payment(
    payment_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user),
    _permission = Depends(require_permission("po_payment", "approve"))
):
    """Approve PO payment (Manager only)"""
    try:
        payment_service = POPaymentService(session)
        success = await payment_service.approve_payment(payment_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to approve payment"
            )
        return {"message": "Payment approved successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving payment {payment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve payment"
        )

@router.post("/{payment_id}/reject")
async def reject_po_payment(
    payment_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Reject PO payment (Manager only)"""
    try:
        payment_service = POPaymentService(session)
        success = await payment_service.reject_payment(payment_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to reject payment"
            )
        return {"message": "Payment rejected successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting payment {payment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject payment"
        )

@router.post("/po/{po_id}/close")
async def close_purchase_order(
    po_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Close purchase order and create final payment (Manager only)"""
    try:
        payment_service = POPaymentService(session)
        success = await payment_service.close_purchase_order(po_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to close purchase order"
            )
        return {"message": "Purchase order closed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing purchase order {po_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to close purchase order"
        )