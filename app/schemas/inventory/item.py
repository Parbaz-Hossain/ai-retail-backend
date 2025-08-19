from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from app.models.shared.enums import UnitType
from app.schemas.inventory.category import Category
from app.schemas.inventory.stock_level import StockLevel
from app.schemas.inventory.stock_type import StockType

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
    qr_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int

    class Config:
        from_attributes = True

class Item(ItemInDB):
    category: Optional['Category'] = None
    stock_type: Optional['StockType'] = None
    stock_levels: List['StockLevel'] = []