"""
Webhook endpoints for task creation based on system events
"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.auth import User
from app.services.task.task_integration_service import TaskIntegrationService
from app.models.inventory.reorder_request import ReorderRequest
from app.models.purchase.purchase_order import PurchaseOrder
from app.models.logistics.shipment import Shipment

router = APIRouter()

@router.post("/inventory/low-stock-check")
async def trigger_low_stock_check(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Manually trigger low stock check and task creation"""
    integration_service = TaskIntegrationService(db)
    await integration_service.check_and_create_low_stock_tasks()
    return {"message": "Low stock check completed and tasks created"}

@router.post("/reorder-request/{request_id}/create-approval-task")
async def create_reorder_approval_task(
    request_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create approval task for reorder request"""
    result = await db.execute(select(ReorderRequest).where(ReorderRequest.id == request_id))
    reorder_request = result.scalar_one_or_none()
    if not reorder_request:
        raise HTTPException(status_code=404, detail="Reorder request not found")
    
    integration_service = TaskIntegrationService(db)
    task = await integration_service.create_reorder_approval_task(reorder_request)
    return {"message": "Approval task created", "task_id": task.id}

@router.post("/purchase-order/{po_id}/create-approval-task")
async def create_purchase_approval_task(
    po_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create approval task for purchase order"""
    result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id))
    purchase_order = result.scalar_one_or_none()
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    integration_service = TaskIntegrationService(db)
    task = await integration_service.create_purchase_approval_task(purchase_order)
    return {"message": "Approval task created", "task_id": task.id}

@router.post("/shipment/{shipment_id}/create-tasks")
async def create_shipment_tasks(
    shipment_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create tasks for shipment management"""
    result = await db.execute(select(Shipment).where(Shipment.id == shipment_id))
    shipment = result.scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    integration_service = TaskIntegrationService(db)
    task = await integration_service.create_shipment_tasks(shipment)
    return {"message": "Shipment tasks created", "task_id": task.id if task else None}

@router.post("/salary/create-monthly-tasks")
async def create_monthly_salary_tasks(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create monthly salary processing tasks"""
    # Check if user has permission (HR role)
    if not current_user.is_superuser:
        role_names = [role.role.name for role in current_user.user_roles if role.is_active]
        if "HR_MANAGER" not in role_names and "ADMIN" not in role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
    
    integration_service = TaskIntegrationService(db)
    await integration_service.create_salary_processing_tasks()
    return {"message": "Monthly salary tasks created"}