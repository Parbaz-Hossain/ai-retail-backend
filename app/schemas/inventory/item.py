from fastapi import Form
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
    available_stock: Decimal
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

class ItemCreateForm:
    def __init__(
        self,
        item_code: str = Form(...),
        name: str = Form(...),
        description: Optional[str] = Form(None),
        category_id: Optional[int] = Form(None),
        stock_type_id: Optional[int] = Form(None),
        unit_type: UnitType = Form(...),
        unit_cost: Optional[Decimal] = Form(None),
        selling_price: Optional[Decimal] = Form(None),
        barcode: Optional[str] = Form(None),
        is_perishable: bool = Form(False),
        shelf_life_days: Optional[int] = Form(None),
        minimum_stock_level: Decimal = Form(0),
        maximum_stock_level: Decimal = Form(0),
        reorder_point: Decimal = Form(0)
    ):
        self.item_code = item_code
        self.name = name
        self.description = description
        self.category_id = category_id
        self.stock_type_id = stock_type_id
        self.unit_type = unit_type
        self.unit_cost = unit_cost
        self.selling_price = selling_price
        self.barcode = barcode
        self.is_perishable = is_perishable
        self.shelf_life_days = shelf_life_days
        self.minimum_stock_level = minimum_stock_level
        self.maximum_stock_level = maximum_stock_level
        self.reorder_point = reorder_point
    
    def to_item_create(self) -> ItemCreate:
        """Convert form data to ItemCreate schema"""
        return ItemCreate(
            item_code=self.item_code,
            name=self.name,
            description=self.description,
            category_id=self.category_id,
            stock_type_id=self.stock_type_id,
            unit_type=self.unit_type,
            unit_cost=self.unit_cost,
            selling_price=self.selling_price,
            barcode=self.barcode,
            is_perishable=self.is_perishable,
            shelf_life_days=self.shelf_life_days,
            minimum_stock_level=self.minimum_stock_level,
            maximum_stock_level=self.maximum_stock_level,
            reorder_point=self.reorder_point
        )

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

class ItemUpdateForm:
    def __init__(
        self,
        item_code: Optional[str] = Form(None),
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        category_id: Optional[int] = Form(None),
        stock_type_id: Optional[int] = Form(None),
        unit_type: Optional[UnitType] = Form(None),
        unit_cost: Optional[Decimal] = Form(None),
        selling_price: Optional[Decimal] = Form(None),
        barcode: Optional[str] = Form(None),
        is_perishable: Optional[bool] = Form(None),
        shelf_life_days: Optional[int] = Form(None),
        minimum_stock_level: Optional[Decimal] = Form(None),
        maximum_stock_level: Optional[Decimal] = Form(None),
        reorder_point: Optional[Decimal] = Form(None),
        is_active: Optional[bool] = Form(None)
    ):
        self.item_code = item_code
        self.name = name
        self.description = description
        self.category_id = category_id
        self.stock_type_id = stock_type_id
        self.unit_type = unit_type
        self.unit_cost = unit_cost
        self.selling_price = selling_price
        self.barcode = barcode
        self.is_perishable = is_perishable
        self.shelf_life_days = shelf_life_days
        self.minimum_stock_level = minimum_stock_level
        self.maximum_stock_level = maximum_stock_level
        self.reorder_point = reorder_point
        self.is_active = is_active
    
    def to_item_update(self) -> ItemUpdate:
        """Convert form data to ItemUpdate schema"""
        return ItemUpdate(
            item_code=self.item_code,
            name=self.name,
            description=self.description,
            category_id=self.category_id,
            stock_type_id=self.stock_type_id,
            unit_type=self.unit_type,
            unit_cost=self.unit_cost,
            selling_price=self.selling_price,
            barcode=self.barcode,
            is_perishable=self.is_perishable,
            shelf_life_days=self.shelf_life_days,
            minimum_stock_level=self.minimum_stock_level,
            maximum_stock_level=self.maximum_stock_level,
            reorder_point=self.reorder_point,
            is_active=self.is_active
        )

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
