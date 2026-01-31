from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from app.models.shared.enums import ReorderRequestStatus, UnitType
from app.schemas.inventory.item import Item
from app.schemas.organization.location_schema import LocationResponse

class ReorderRequestItemBase(BaseModel):
    item_id: int
    unit_type: UnitType
    requested_quantity: Decimal
    reason: Optional[str] = None

    @validator('requested_quantity')
    def validate_positive_quantity(cls, v):
        if v <= 0:
            raise ValueError('Requested quantity must be positive')
        return v

class ReorderRequestItemCreate(ReorderRequestItemBase):
    pass

class ReorderRequestItemInDB(ReorderRequestItemBase):
    id: int
    reorder_request_id: int
    current_stock: Decimal
    approved_quantity: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ReorderRequestItem(ReorderRequestItemInDB):
    item: Optional['Item'] = None

class ReorderRequestBase(BaseModel):
    location_id: int        # From which location (warehouse) requesting
    to_location_id: int     # To which location the items should go
    request_date: Optional[date] = None
    required_date: Optional[date] = None
    notes: Optional[str] = None

class ReorderRequestCreate(ReorderRequestBase):
    pass

class ReorderRequestUpdate(BaseModel):
    to_location_id: Optional[int] = None
    required_date: Optional[date] = None
    notes: Optional[str] = None
    status: Optional[ReorderRequestStatus] = None

class ReorderRequestInDB(ReorderRequestBase):
    id: int
    request_number: str
    status: ReorderRequestStatus
    requested_by: int
    approved_by: Optional[int] = None
    approved_date: Optional[datetime] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ReorderRequest(ReorderRequestInDB):
    location: Optional['LocationResponse'] = None
    to_location: Optional['LocationResponse'] = None
    items: List[ReorderRequestItem] = Field(default_factory=list)