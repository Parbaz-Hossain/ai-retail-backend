from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from decimal import Decimal

from app.models.shared.enums import UnitType

# --- Lightweight refs to avoid circular imports ---
class ItemRef(BaseModel):
    id: int
    item_code: str
    name: str
    unit_type: Optional[UnitType] = None

class LocationRef(BaseModel):
    id: int
    name: str
# ---------------------------------------------------

class StockLevelBase(BaseModel):
    item_id: int
    location_id: int
    current_stock: Decimal = 0
    reserved_stock: Decimal = 0
    par_level_min: Decimal = 0
    par_level_max: Decimal = 0

    @validator('current_stock', 'reserved_stock', 'par_level_min', 'par_level_max')
    def validate_non_negative(cls, v):
        if v < 0:
            raise ValueError('Stock levels cannot be negative')
        return v

class StockLevelCreate(StockLevelBase):
    unit_type: UnitType

class StockLevelUpdate(BaseModel):
    current_stock: Optional[Decimal] = None
    reserved_stock: Optional[Decimal] = None
    par_level_min: Optional[Decimal] = None
    par_level_max: Optional[Decimal] = None

class StockLevelInDB(StockLevelBase):
    id: int
    available_stock: Decimal
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class StockLevel(StockLevelInDB):
    item: Optional[ItemRef] = None
    location: Optional[LocationRef] = None

class LowStockItem(BaseModel):
    item: ItemRef
    stock_level: StockLevel
    shortage: Decimal

StockLevel.model_rebuild()
LowStockItem.model_rebuild()
