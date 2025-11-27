from decimal import Decimal
from pydantic import BaseModel, ConfigDict, validator, EmailStr
from typing import Optional
from datetime import datetime

class LocationBase(BaseModel):
    name: str
    location_type: str  # BRANCH or WAREHOUSE
    manager_id: Optional[int] = None
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
        if v not in ['BRANCH', 'WAREHOUSE', 'CENTRAL_KITCHEN']:
            raise ValueError('Location type must be BRANCH or WAREHOUSE or CENTRAL_KITCHEN')
        return v
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Location name must be at least 2 characters')
        return v.strip()

class LocationUpdate(BaseModel):
    name: Optional[str] = None
    location_type: Optional[str] = None
    manager_id: Optional[int] = None
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

class ManagerRef(BaseModel):
    username: str
    full_name: str
    email: Optional[EmailStr] = None

    class Config:
        from_attributes = True

class LocationSpecificResponse(LocationBase):
    id: int
    manager: Optional[ManagerRef] = None
    is_active: bool = None
    created_at: datetime = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class LocationResponse(LocationBase):
    id: int
    is_active: bool = None
    created_at: datetime = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True