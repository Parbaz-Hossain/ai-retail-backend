from pydantic import BaseModel, validator
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

class RefillItemRequest(BaseModel):
    item_id: int
    quantity: Decimal
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be greater than 0')
        return v

class RefillKitchenRequest(BaseModel):
    location_id: int  # The kitchen location
    items: List[RefillItemRequest]
    remarks: Optional[str] = None
    
    @validator('items')
    def validate_items(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one item is required')
        return v

class RawMaterialUsage(BaseModel):
    ingredient_item_id: int
    ingredient_item_name: str
    total_quantity: Decimal
    unit_type: str
    stock_movement_id: Optional[int] = None

class RefillItemResult(BaseModel):
    item_id: int
    item_name: str
    refill_quantity: Decimal
    raw_materials_used: List[RawMaterialUsage]
    inbound_movement_id: int

class RefillKitchenResponse(BaseModel):
    location_id: int
    total_items_refilled: int
    refill_results: List[RefillItemResult]
    message: str
    refilled_at: datetime