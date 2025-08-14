from pydantic import BaseModel, validator
from typing import Optional
from datetime import date, datetime

class HolidayBase(BaseModel):
    name: str
    date: date
    description: Optional[str] = None
    is_recurring: bool = False

class HolidayCreate(HolidayBase):
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Holiday name must be at least 2 characters')
        return v.strip()

class HolidayUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[date] = None
    description: Optional[str] = None
    is_recurring: Optional[bool] = None
    is_active: Optional[bool] = None

class HolidayResponse(HolidayBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True