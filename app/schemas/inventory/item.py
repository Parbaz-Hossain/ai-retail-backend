from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from app.models.shared.enums import UnitType

# --- Lightweight refs to avoid circular imports ---
class CategoryRef(BaseModel):
    id: int
    name: str

class StockTypeRef(BaseModel):
    id: int
    name: str

class StockLevelRef(BaseModel):
    id: int
    location_id: int
    current_stock: Decimal
# ---------------------------------------------------

class ItemBase(BaseModel):
    item_code: str
    name: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    stock_type_id: Optional[int] = None
    unit_type: UnitType
    unit_cost: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    barcode: Optional[str] = None
    image_url: Optional[str] = None
    is_perishable: bool = False
    shelf_life_days: Optional[int] = None
    minimum_stock_level: Decimal = 0
    maximum_stock_level: Decimal = 0
    reorder_point: Decimal = 0

    @validator('unit_cost', 'selling_price', pre=True)
    def validate_prices(cls, v):
        if v is not None and v < 0:
            raise ValueError('Price cannot be negative')
        return v

class ItemCreate(ItemBase):
    qr_code: Optional[str] = None

class ItemUpdate(BaseModel):
    item_code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    stock_type_id: Optional[int] = None
    unit_type: Optional[UnitType] = None
    unit_cost: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    barcode: Optional[str] = None
    image_url: Optional[str] = None
    is_perishable: Optional[bool] = None
    shelf_life_days: Optional[int] = None
    minimum_stock_level: Optional[Decimal] = None
    maximum_stock_level: Optional[Decimal] = None
    reorder_point: Optional[Decimal] = None
    is_active: Optional[bool] = None

class ItemInDB(ItemBase):
    id: int
    qr_code: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Item(ItemInDB):
    # Use local Ref models to avoid importing other modules
    category: Optional[CategoryRef] = None
    stock_type: Optional[StockTypeRef] = None
    stock_levels: Optional[List[StockLevelRef]] = None

Item.model_rebuild() 
