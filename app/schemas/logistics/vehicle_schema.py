from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

class VehicleBase(BaseModel):
    vehicle_number: str
    vehicle_type: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    capacity_weight: Optional[Decimal] = None
    capacity_volume: Optional[Decimal] = None
    fuel_type: Optional[str] = None
    registration_expiry: Optional[date] = None
    insurance_expiry: Optional[date] = None
    last_maintenance_date: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    current_mileage: Optional[int] = None
    is_available: bool = True
    is_active: bool = True

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    vehicle_number: Optional[str] = None
    vehicle_type: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    capacity_weight: Optional[Decimal] = None
    capacity_volume: Optional[Decimal] = None
    fuel_type: Optional[str] = None
    registration_expiry: Optional[date] = None
    insurance_expiry: Optional[date] = None
    last_maintenance_date: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    current_mileage: Optional[int] = None
    is_available: Optional[bool] = None
    is_active: Optional[bool] = None

class VehicleResponse(VehicleBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True