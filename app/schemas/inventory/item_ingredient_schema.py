from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime
from decimal import Decimal
from app.models.shared.enums import UnitType

# Lightweight reference for ingredient item
class IngredientItemRef(BaseModel):
    id: int
    name: str
    item_code: Optional[str] = None
    unit_type: UnitType
    unit_cost: Optional[Decimal] = None
    
    class Config:
        from_attributes = True

class ItemIngredientBase(BaseModel):
    ingredient_item_id: int
    quantity: Decimal
    unit_type: UnitType
    description: Optional[str] = None
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be greater than 0')
        return v

class ItemIngredientCreate(ItemIngredientBase):
    pass

class ItemIngredientUpdate(BaseModel):
    quantity: Optional[Decimal] = None
    unit_type: Optional[UnitType] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Quantity must be greater than 0')
        return v

class ItemIngredientResponse(ItemIngredientBase):
    id: int
    item_id: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Include ingredient item details
    ingredient_item: Optional[IngredientItemRef] = None
    
    class Config:
        from_attributes = True