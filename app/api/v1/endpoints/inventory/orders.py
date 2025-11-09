import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.core.config import settings
from app.models.auth.user import User
from app.models.shared.enums import OrderStatus
from app.services.inventory.foodics_order_service import FoodicsOrderService
from app.schemas.inventory.order_schema import (
    Order, 
    FoodicsSyncRequest, 
    FoodicsSyncResponse,
    OrderSummary
)
from app.schemas.common.pagination import PaginatedResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/sync", response_model=FoodicsSyncResponse)
async def sync_foodics_orders(
    request: FoodicsSyncRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Sync orders from Foodics API.
    Can sync all locations or a specific location.
    """
    try:
        # Get Foodics API token from settings
        foodics_token = getattr(settings, 'FOODICS_API_TOKEN', None)
        if not foodics_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Foodics API token not configured"
            )
        
        service = FoodicsOrderService(db, foodics_token)
        result = await service.fetch_and_save_orders(request.location_id)
        
        return FoodicsSyncResponse(**result)
        
    except Exception as e:
        logger.error(f"Sync orders error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync orders: {str(e)}"
        )

@router.get("/summary", response_model=OrderSummary)
async def get_orders_summary(
    location_id: Optional[int] = Query(None),
    status: Optional[OrderStatus] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get orders summary statistics with filters.
    Returns: Total Payments, Total Sales, Total Discount Amount, Orders Count, Returned Orders
    """
    try:
        foodics_token = getattr(settings, 'FOODICS_API_TOKEN', None)
        if not foodics_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Foodics API token not configured"
            )
        
        service = FoodicsOrderService(db, foodics_token)
        summary = await service.get_order_summary(
            location_id=location_id,
            status=status,
            start_date=start_date,
            end_date=end_date
        )
        
        return OrderSummary(**summary)
        
    except Exception as e:
        logger.error(f"Get orders summary error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get orders summary"
        )

@router.get("/", response_model=PaginatedResponse[Order])
async def get_orders(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    location_id: Optional[int] = Query(None),
    status: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get orders with pagination and filters"""
    try:
        foodics_token = getattr(settings, 'FOODICS_API_TOKEN', None)
        if not foodics_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Foodics API token not configured"
            )
        
        service = FoodicsOrderService(db, foodics_token)
        orders = await service.get_orders(
            page_index=page_index,
            page_size=page_size,
            location_id=location_id,
            status=status,
            start_date=start_date,
            end_date=end_date
        )
        return orders
        
    except Exception as e:
        logger.error(f"Get orders error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get orders"
        )

@router.get("/{order_id}", response_model=Order)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get order by ID with all details"""
    try:
        foodics_token = getattr(settings, 'FOODICS_API_TOKEN', None)
        if not foodics_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Foodics API token not configured"
            )
        
        service = FoodicsOrderService(db, foodics_token)
        order = await service.get_order_by_id(order_id)
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        return order
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get order error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get order"
        )