from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StockTypeBase(BaseModel):
    name: str
    description: Optional[str] = None

class StockTypeCreate(StockTypeBase):
    pass

class StockTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class StockTypeInDB(StockTypeBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int

    class Config:
        from_attributes = True

class StockType(StockTypeInDB):
    pass
