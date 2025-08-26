from decimal import Decimal
from pydantic import BaseModel, ConfigDict, validator, EmailStr
from typing import Optional
from datetime import datetime

class LocationBase(BaseModel):
    name: str
    location_type: str  # BRANCH or WAREHOUSE
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "Saudi Arabia"
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)

class LocationCreate(LocationBase):
    @validator('location_type')
    def validate_location_type(cls, v):
        if v not in ['BRANCH', 'WAREHOUSE']:
            raise ValueError('Location type must be BRANCH or WAREHOUSE')
        return v
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Location name must be at least 2 characters')
        return v.strip()

class LocationUpdate(BaseModel):
    name: Optional[str] = None
    location_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

class LocationResponse(LocationBase):
    id: int
    is_active: bool = None
    created_at: datetime = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True