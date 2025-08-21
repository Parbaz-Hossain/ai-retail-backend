# app/api/v1/endpoints/purchase/goods_receipts.py
import logging
from typing import Any, List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.services.purchase.goods_receipt_service import GoodsReceiptService
from app.schemas.purchase.goods_receipt_schema import (GoodsReceiptCreate, GoodsReceiptUpdate, GoodsReceiptResponse)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=GoodsReceiptResponse, status_code=status.HTTP_201_CREATED)
async def create_goods_receipt(
    receipt_data: GoodsReceiptCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Create a new goods receipt"""
    try:
        receipt_service = GoodsReceiptService(session)
        receipt = await receipt_service.create_goods_receipt(receipt_data, current_user.id)
        return receipt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating goods receipt: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create goods receipt"
        )

@router.get("/", response_model=List[GoodsReceiptResponse])
async def get_goods_receipts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    supplier_id: Optional[int] = Query(None),
    purchase_order_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Get goods receipts with pagination and filters"""
    try:
        receipt_service = GoodsReceiptService(session)
        result = await receipt_service.get_goods_receipts(
            skip=skip,
            limit=limit,
            supplier_id=supplier_id,
            purchase_order_id=purchase_order_id,
            start_date=start_date,
            end_date=end_date,
            search=search
        )
        return result
    except Exception as e:
        logger.error(f"Error getting goods receipts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get goods receipts"
        )

@router.get("/{receipt_id}", response_model=GoodsReceiptResponse)
async def get_goods_receipt(
    receipt_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get goods receipt by ID"""
    try:
        receipt_service = GoodsReceiptService(session)
        receipt = await receipt_service.get_goods_receipt(receipt_id)
        if not receipt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Goods receipt not found"
            )
        return receipt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting goods receipt {receipt_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get goods receipt"
        )

@router.put("/{receipt_id}", response_model=GoodsReceiptResponse)
async def update_goods_receipt(
    receipt_id: int,
    receipt_data: GoodsReceiptUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update goods receipt"""
    try:
        receipt_service = GoodsReceiptService(session)
        receipt = await receipt_service.update_goods_receipt(receipt_id, receipt_data, current_user.id)
        if not receipt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Goods receipt not found"
            )
        return receipt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating goods receipt {receipt_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update goods receipt"
        )

@router.delete("/{receipt_id}")
async def delete_goods_receipt(
    receipt_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Delete goods receipt and reverse stock movements"""
    try:
        receipt_service = GoodsReceiptService(session)
        success = await receipt_service.delete_goods_receipt(receipt_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Goods receipt not found"
            )
        return {"message": "Goods receipt deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting goods receipt {receipt_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete goods receipt"
        )