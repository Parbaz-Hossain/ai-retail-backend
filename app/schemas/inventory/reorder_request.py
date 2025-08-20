from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from app.models.shared.enums import ReorderRequestStatus
from app.schemas.inventory.item import Item
from app.schemas.organization.location_schema import LocationResponse

class ReorderRequestItemBase(BaseModel):
    item_id: int
    requested_quantity: Decimal
    estimated_unit_cost: Optional[Decimal] = None
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
    estimated_total_cost: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ReorderRequestItem(ReorderRequestItemInDB):
    item: Optional['Item'] = None

class ReorderRequestBase(BaseModel):
    location_id: int
    request_date: Optional[date] = None
    required_date: Optional[date] = None
    priority: str = "NORMAL"
    notes: Optional[str] = None

class ReorderRequestCreate(ReorderRequestBase):
    items: List[ReorderRequestItemCreate]

    @validator('items')
    def validate_items_not_empty(cls, v):
        if not v:
            raise ValueError('At least one item is required')
        return v

class ReorderRequestUpdate(BaseModel):
    required_date: Optional[date] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[ReorderRequestStatus] = None

class ReorderRequestInDB(ReorderRequestBase):
    id: int
    request_number: str
    status: ReorderRequestStatus
    total_estimated_cost: Optional[Decimal]
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
    items: List[ReorderRequestItem] = Field(default_factory=list)