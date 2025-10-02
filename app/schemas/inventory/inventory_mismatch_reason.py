from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InventoryMismatchReasonBase(BaseModel):
    name: str
    description: Optional[str] = None

class InventoryMismatchReasonCreate(InventoryMismatchReasonBase):
    pass

class InventoryMismatchReasonUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class InventoryMismatchReasonInDB(InventoryMismatchReasonBase):
    id: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class InventoryMismatchReason(InventoryMismatchReasonInDB):
    pass