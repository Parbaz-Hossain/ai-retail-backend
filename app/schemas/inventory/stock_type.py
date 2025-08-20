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
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True

class StockType(StockTypeInDB):
    pass
