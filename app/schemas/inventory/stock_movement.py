from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
from app.models.shared.enums import StockMovementType, UnitType
from app.schemas.inventory.item import Item
from app.schemas.organization.location_schema import LocationResponse

class StockMovementBase(BaseModel):
    item_id: int
    location_id: int
    movement_type: StockMovementType
    quantity: Decimal
    unit_cost: Optional[Decimal] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    remarks: Optional[str] = None

    @validator('quantity')
    def validate_positive_quantity(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return v

class StockMovementCreate(StockMovementBase):
    total_cost: Optional[Decimal] = None
    unit_type: UnitType

class StockMovementBaseResponse(BaseModel):
    item_id: int
    location_id: int
    movement_type: StockMovementType
    quantity: Decimal
    unit_cost: Optional[Decimal] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    remarks: Optional[str] = None

class StockMovementInDB(StockMovementBaseResponse):
    id: int
    total_cost: Optional[Decimal]
    performed_by: Optional[int] = None
    movement_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True

class ItemRef(BaseModel):
    id: int
    name: str
    item_code: Optional[str] = None
    unit_type: Optional[UnitType] = None

    class Config:
        from_attributes = True

class StockMovement(StockMovementInDB):
    item: Optional[ItemRef] = None
    location: Optional['LocationResponse'] = None