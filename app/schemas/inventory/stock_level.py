from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from decimal import Decimal

from app.schemas.inventory.item import Item
from app.schemas.organization.location_schema import LocationResponse

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
    pass

class StockLevelUpdate(BaseModel):
    current_stock: Optional[Decimal] = None
    reserved_stock: Optional[Decimal] = None
    par_level_min: Optional[Decimal] = None
    par_level_max: Optional[Decimal] = None

class StockLevelInDB(StockLevelBase):
    id: int
    available_stock: Decimal
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int

    class Config:
        from_attributes = True

class StockLevel(StockLevelInDB):
    item: Optional['Item'] = None
    location: Optional['LocationResponse'] = None


class LowStockItem(BaseModel):
    item: Item
    stock_level: StockLevel
    shortage: Decimal