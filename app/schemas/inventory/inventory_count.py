from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal

from app.schemas.inventory.item import Item
from app.schemas.organization.location_schema import LocationResponse

class InventoryCountItemBase(BaseModel):
    item_id: int
    system_quantity: Decimal
    counted_quantity: Decimal
    unit_cost: Optional[Decimal] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    remarks: Optional[str] = None

class InventoryCountItemCreate(InventoryCountItemBase):
    pass

class InventoryCountItemInDB(InventoryCountItemBase):
    id: int
    inventory_count_id: int
    variance_quantity: Decimal
    variance_value: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int

    class Config:
        from_attributes = True

class InventoryCountItem(InventoryCountItemInDB):
    item: Optional['Item'] = None

class InventoryCountBase(BaseModel):
    location_id: int
    count_date: date
    count_type: str = "FULL"
    notes: Optional[str] = None

class InventoryCountCreate(InventoryCountBase):
    items: List[InventoryCountItemCreate] = []

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
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int

    class Config:
        from_attributes = True

class InventoryCount(InventoryCountInDB):
    location: Optional['LocationResponse'] = None
    items: List[InventoryCountItem] = []