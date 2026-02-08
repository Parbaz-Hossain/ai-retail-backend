from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal

from app.models.shared.enums import UnitType

class ItemRef(BaseModel):
    id: int
    name: str
    item_code: Optional[str] = None
    unit_type: Optional[UnitType] = None
    class Config:
        from_attributes = True

class ReasonRef(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

class InventoryCountItemBase(BaseModel):
    item_id: int
    system_quantity: Decimal
    counted_quantity: Decimal
    reason_id: Optional[int] = None
    expiry_date: Optional[date] = None
    remarks: Optional[str] = None

class InventoryCountItemCreate(InventoryCountItemBase):
    unit_type: UnitType

class InventoryCountItemInDB(InventoryCountItemBase):
    id: int
    inventory_count_id: int
    variance_quantity: Decimal
    variance_value: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

# ✅ items are InventoryCountItem, each with a shallow ItemRef
class InventoryCountItem(InventoryCountItemInDB):
    item: Optional[ItemRef] = None
    reason: Optional[ReasonRef] = None

class InventoryCountBase(BaseModel):
    location_id: int
    count_date: date
    count_type: str = "FULL"
    notes: Optional[str] = None

class InventoryCountCreate(InventoryCountBase):
    pass

class InventoryCountUpdate(BaseModel):
    count_date: Optional[date] = None
    count_type: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class InventoryCountInDB(InventoryCountBase):
    id: int
    count_number: str
    status: str
    conducted_by: Optional[int] = None
    verified_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class LocationRef(BaseModel):
    id: int
    name: str
    location_type: str
    city: Optional[str] = None
    country: Optional[str] = None
    class Config:
        from_attributes = True

class InventoryCount(InventoryCountInDB):
    location: Optional[LocationRef] = None
    items: List[InventoryCountItem] = Field(default_factory=list)  # ✅
