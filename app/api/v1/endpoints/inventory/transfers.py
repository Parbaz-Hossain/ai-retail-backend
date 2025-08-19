from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict
from decimal import Decimal
from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.services.inventory.transfer_service import TransferService
from app.schemas.inventory.transfer import Transfer, TransferCreate, TransferUpdate
from app.models.shared.enums import TransferStatus
from app.models.auth.user import User
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()

@router.post("/", response_model=Transfer, status_code=status.HTTP_201_CREATED)
async def create_transfer(
    transfer_data: TransferCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new transfer"""
    try:
        service = TransferService(db)
        transfer = await service.create_transfer(transfer_data, current_user.id)
        return transfer
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[Transfer])
async def get_transfers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    from_location_id: Optional[int] = Query(None),
    to_location_id: Optional[int] = Query(None),
    status: Optional[TransferStatus] = Query(None),
    db: AsyncSession = Depends(get_async_session)
):
    """Get all transfers with optional filters"""
    service = TransferService(db)
    transfers = await service.get_transfers(
        skip=skip, 
        limit=limit,
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        status=status
    )
    return transfers

@router.get("/{transfer_id}", response_model=Transfer)
async def get_transfer(
    transfer_id: int,
    db: AsyncSession = Depends(get_async_session)
):
    """Get transfer by ID"""
    service = TransferService(db)
    transfer = await service.get_transfer_by_id(transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return transfer

@router.post("/{transfer_id}/approve", response_model=Transfer)
async def approve_transfer(
    transfer_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Approve transfer and reserve stock"""
    try:
        service = TransferService(db)
        transfer = await service.approve_transfer(transfer_id, current_user.id)
        return transfer
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Transfer not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{transfer_id}/send", response_model=Transfer)
async def send_transfer(
    transfer_id: int,
    sent_quantities: Dict[int, Decimal],
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Mark transfer as sent with actual quantities"""
    try:
        service = TransferService(db)
        transfer = await service.send_transfer(transfer_id, sent_quantities, current_user.id)
        return transfer
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Transfer not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{transfer_id}/receive", response_model=Transfer)
async def receive_transfer(
    transfer_id: int,
    received_quantities: Dict[int, Decimal],
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Mark transfer as received with actual quantities"""
    try:
        service = TransferService(db)
        transfer = await service.receive_transfer(transfer_id, received_quantities, current_user.id)
        return transfer
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Transfer not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{transfer_id}/cancel", response_model=Transfer)
async def cancel_transfer(
    transfer_id: int,
    reason: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Cancel transfer and release reserved stock"""
    try:
        service = TransferService(db)
        transfer = await service.cancel_transfer(transfer_id, reason, current_user.id)
        return transfer
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Transfer not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))