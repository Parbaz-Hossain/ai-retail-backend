from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, validator
from datetime import datetime

from app.models.shared.enums import UnitType

class ItemSupplierBase(BaseModel):
    item_id: int
    supplier_id: int
    supplier_item_code: Optional[str] = None
    unit_type: UnitType
    unit_cost: Decimal
    minimum_order_quantity: Decimal = Decimal('1')
    lead_time_days: int = 0
    is_preferred: bool = False

    @validator('unit_cost', 'minimum_order_quantity')
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('Unit cost and minimum order quantity must be positive')
        return v

    @validator('lead_time_days')
    def validate_lead_time(cls, v):
        if v < 0:
            raise ValueError('Lead time days cannot be negative')
        return v

class ItemSupplierCreate(ItemSupplierBase):
    pass

class ItemSupplierUpdate(BaseModel):
    supplier_item_code: Optional[str] = None
    unit_cost: Optional[Decimal] = None
    minimum_order_quantity: Optional[Decimal] = None
    lead_time_days: Optional[int] = None
    is_preferred: Optional[bool] = None

class ItemInfo(BaseModel):
    item_code: str
    name: str
    unit_type: UnitType

    class Config:
        from_attributes = True

class SupplierInfo(BaseModel):
    name: str

    class Config:
        from_attributes = True

class ItemSupplierResponse(ItemSupplierBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    item: Optional[ItemInfo] = None
    supplier: Optional[SupplierInfo] = None

    class Config:
        from_attributes = True