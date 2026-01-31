from fastapi import Form
from pydantic import BaseModel, validator, field_serializer
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from app.models.shared.enums import UnitType

# --- Lightweight refs to avoid circular imports ---
class CategoryRef(BaseModel):
    id: int
    name: str

class ItemRef(BaseModel):
    id: int
    name: str
    unit_type: UnitType
# ---------------------------------------------------

class ProductItemBase(BaseModel):
    item_id: int
    quantity: Decimal
    unit_cost: Optional[Decimal] = None
    notes: Optional[str] = None

    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be greater than 0')
        return v

class ProductItemCreate(ProductItemBase):    
    unit_type: UnitType

class ProductItemUpdate(BaseModel):
    item_id: Optional[int] = None
    quantity: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    notes: Optional[str] = None

class ProductItemInDB(ProductItemBase):
    id: int
    product_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ProductItem(ProductItemInDB):
    item: Optional[ItemRef] = None

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    selling_price: Optional[Decimal] = None
    preparation_time: Optional[int] = None
    barcode: Optional[str] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None

    @validator('selling_price')
    def validate_selling_price(cls, v):
        if v < 0:
            raise ValueError('Selling price cannot be negative')
        return v

    @validator('preparation_time')
    def validate_preparation_time(cls, v):
        if v is not None and v < 0:
            raise ValueError('Preparation time cannot be negative')
        return v

class ProductCreate(ProductBase):
    pass

class ProductCreateForm:
    def __init__(
        self,
        name: str = Form(...),
        description: Optional[str] = Form(None),
        category_id: Optional[int] = Form(None),
        selling_price: Optional[Decimal] = Form(None),
        preparation_time: Optional[int] = Form(None),
        barcode: Optional[str] = Form(None),
        is_available: Optional[bool] = Form(None)
    ):
        self.name = name
        self.description = description
        self.category_id = category_id
        self.selling_price = selling_price
        self.preparation_time = preparation_time
        self.barcode = barcode
        self.is_available = is_available
    
    def to_product_create(self) -> ProductCreate:        
        return ProductCreate(
            name=self.name,
            description=self.description,
            category_id=self.category_id,
            selling_price=self.selling_price,
            preparation_time=self.preparation_time,
            barcode=self.barcode,
            is_available=self.is_available
        )

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    selling_price: Optional[Decimal] = None
    preparation_time: Optional[int] = None
    barcode: Optional[str] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None
    is_active: Optional[bool] = None

class ProductUpdateForm:
    def __init__(
        self,
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        category_id: Optional[int] = Form(None),
        selling_price: Optional[Decimal] = Form(None),
        preparation_time: Optional[int] = Form(None),
        barcode: Optional[str] = Form(None),
        is_available: Optional[bool] = Form(None),
        is_active: Optional[bool] = Form(None)
    ):
        self.name = name
        self.description = description
        self.category_id = category_id
        self.selling_price = selling_price
        self.preparation_time = preparation_time
        self.barcode = barcode
        self.is_available = is_available
        self.is_active = is_active
    
    def to_product_update(self) -> ProductUpdate:        
        return ProductUpdate(
            name=self.name,
            description=self.description,
            category_id=self.category_id,
            selling_price=self.selling_price,
            preparation_time=self.preparation_time,
            barcode=self.barcode,
            is_available=self.is_available,
            is_active=self.is_active
        )

class ProductInDB(ProductBase):
    id: int
    product_guid: UUID
    product_code: Optional[str] = None
    qr_code: Optional[str] = None
    cost_price: Optional[Decimal] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_serializer('product_guid')
    def serialize_uuid(self, value: UUID) -> str:
        return str(value)

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True

class ProductResponse(ProductInDB):
    category: Optional[CategoryRef] = None
    product_items: Optional[List[ProductItem]] = None


ProductResponse.model_rebuild()