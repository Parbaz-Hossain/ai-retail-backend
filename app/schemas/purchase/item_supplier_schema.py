from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, validator
from datetime import datetime

class ItemSupplierBase(BaseModel):
    item_id: int
    supplier_id: int
    supplier_item_code: Optional[str] = None
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

class ItemSupplierResponse(ItemSupplierBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    item_name: Optional[str] = None
    item_code: Optional[str] = None
    supplier_name: Optional[str] = None

    class Config:
        from_attributes = True