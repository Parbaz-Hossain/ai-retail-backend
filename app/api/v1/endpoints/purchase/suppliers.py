import logging
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.schemas.common.pagination import PaginatedResponse
from app.services.purchase.supplier_service import SupplierService
from app.schemas.purchase.supplier_schema import (SupplierCreate, SupplierUpdate, SupplierResponse)
from app.schemas.purchase.item_supplier_schema import (ItemSupplierCreate, ItemSupplierResponse)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    supplier_data: SupplierCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Create a new supplier"""
    try:
        supplier_service = SupplierService(session)
        supplier = await supplier_service.create_supplier(supplier_data, current_user.id)
        return supplier
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating supplier: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create supplier"
        )

@router.get("/", response_model=PaginatedResponse[SupplierResponse])
async def get_suppliers(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: str = Query(None),
    is_active: bool = Query(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Get suppliers with pagination and filters"""
    try:
        supplier_service = SupplierService(session)
        result = await supplier_service.get_suppliers(
            page_index=page_index,
            page_size=page_size,
            search=search,
            is_active=is_active
        )
        return result
    except Exception as e:
        logger.error(f"Error getting suppliers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get suppliers"
        )

@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get supplier by ID"""
    try:
        supplier_service = SupplierService(session)
        supplier = await supplier_service.get_supplier(supplier_id)
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found"
            )
        return supplier
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting supplier {supplier_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get supplier"
        )

@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    supplier_data: SupplierUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update supplier"""
    try:
        supplier_service = SupplierService(session)
        supplier = await supplier_service.update_supplier(supplier_id, supplier_data, current_user.id)
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found"
            )
        return supplier
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating supplier {supplier_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update supplier"
        )

@router.delete("/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Delete supplier"""
    try:
        supplier_service = SupplierService(session)
        success = await supplier_service.delete_supplier(supplier_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found"
            )
        return {"message": "Supplier deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting supplier {supplier_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete supplier"
        )

@router.post("/{supplier_id}/items", response_model=ItemSupplierResponse)
async def add_item_to_supplier(
    supplier_id: int,
    item_data: ItemSupplierCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Add item to supplier"""
    try:
        supplier_service = SupplierService(session)
        item_supplier = await supplier_service.add_item_to_supplier(
            supplier_id=supplier_id,
            item_id=item_data.item_id,
            supplier_item_code=item_data.supplier_item_code,
            unit_cost=item_data.unit_cost,
            minimum_order_quantity=item_data.minimum_order_quantity,
            lead_time_days=item_data.lead_time_days,
            is_preferred=item_data.is_preferred,
            user_id=current_user.id
        )
        return item_supplier
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding item to supplier: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add item to supplier"
        )

@router.delete("/{supplier_id}/items/{item_id}")
async def remove_item_from_supplier(
    supplier_id: int,
    item_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Remove item from supplier"""
    try:
        supplier_service = SupplierService(session)
        success = await supplier_service.remove_item_from_supplier(
            supplier_id, item_id, current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item-supplier relationship not found"
            )
        return {"message": "Item removed from supplier successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing item from supplier: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove item from supplier"
        )

@router.get("/{supplier_id}/items", response_model=List[ItemSupplierResponse])
async def get_supplier_items(
    supplier_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get all items for a supplier"""
    try:
        supplier_service = SupplierService(session)
        items = await supplier_service.get_supplier_items(supplier_id)
        return items
    except Exception as e:
        logger.error(f"Error getting supplier items: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get supplier items"
        )