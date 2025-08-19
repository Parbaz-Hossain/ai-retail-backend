from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from app.models.shared.enums import TransferStatus
from app.schemas.inventory.item import Item
from app.schemas.organization.location_schema import LocationResponse

class TransferItemBase(BaseModel):
    item_id: int
    requested_quantity: Decimal
    unit_cost: Optional[Decimal] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None

    @validator('requested_quantity')
    def validate_positive_quantity(cls, v):
        if v <= 0:
            raise ValueError('Requested quantity must be positive')
        return v

class TransferItemCreate(TransferItemBase):
    pass

class TransferItemInDB(TransferItemBase):
    id: int
    transfer_id: int
    sent_quantity: Optional[Decimal] = None
    received_quantity: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int

    class Config:
        from_attributes = True

class TransferItem(TransferItemInDB):
    item: Optional['Item'] = None

class TransferBase(BaseModel):
    from_location_id: int
    to_location_id: int
    transfer_date: Optional[date] = None
    expected_date: Optional[date] = None
    notes: Optional[str] = None

    @validator('to_location_id')
    def validate_different_locations(cls, v, values):
        if 'from_location_id' in values and v == values['from_location_id']:
            raise ValueError('From and to locations must be different')
        return v

class TransferCreate(TransferBase):
    items: List[TransferItemCreate]

    @validator('items')
    def validate_items_not_empty(cls, v):
        if not v:
            raise ValueError('At least one item is required')
        return v

class TransferUpdate(BaseModel):
    expected_date: Optional[date] = None
    notes: Optional[str] = None
    status: Optional[TransferStatus] = None

class TransferInDB(TransferBase):
    id: int
    transfer_number: str
    status: TransferStatus
    requested_by: int
    approved_by: Optional[int] = None
    sent_by: Optional[int] = None
    received_by: Optional[int] = None
    approved_date: Optional[datetime] = None
    sent_date: Optional[datetime] = None
    received_date: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int

    class Config:
        from_attributes = True

class Transfer(TransferInDB):
    from_location: Optional['LocationResponse'] = None
    to_location: Optional['LocationResponse'] = None
    items: List[TransferItem] = []