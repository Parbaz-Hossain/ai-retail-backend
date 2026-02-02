from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from app.models.shared.enums import ShipmentStatus, UnitType
from app.schemas.logistics.driver_schema import DriverResponse
from app.schemas.logistics.vehicle_schema import VehicleResponse
from app.schemas.organization.location_schema import LocationResponse

class ShipmentItemBase(BaseModel):
    item_id: int
    quantity: Decimal
    weight: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    packaging_type: Optional[str] = None
    special_handling: Optional[str] = None

class ShipmentItemCreate(ShipmentItemBase):
    unit_type: UnitType

class ItemResponse(BaseModel):
    item_code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None

class ShipmentItemResponse(ShipmentItemBase):
    id: int
    shipment_id: int
    delivered_quantity: Optional[Decimal] = None
    item: Optional[ItemResponse] = None

    class Config:
        from_attributes = True

class ShipmentBase(BaseModel):
    from_location_id: int
    to_location_id: int
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    shipment_date: date
    expected_delivery_date: Optional[date] = None
    distance_km: Optional[Decimal] = None
    fuel_cost: Optional[Decimal] = None
    notes: Optional[str] = None

class ShipmentCreate(ShipmentBase):
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None

class ShipmentUpdate(BaseModel):
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    expected_delivery_date: Optional[date] = None
    distance_km: Optional[Decimal] = None
    fuel_cost: Optional[Decimal] = None
    notes: Optional[str] = None

class ShipmentResponse(ShipmentBase):
    id: int
    shipment_number: str
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    status: ShipmentStatus
    pickup_otp_verified: bool = False
    delivery_otp_verified: bool = False
    pickup_time: Optional[datetime] = None
    delivery_time: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    total_weight: Optional[Decimal] = None
    total_volume: Optional[Decimal] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Related objects
    from_location: Optional[LocationResponse] = None
    to_location: Optional[LocationResponse] = None
    driver: Optional[DriverResponse] = None
    vehicle: Optional[VehicleResponse] = None
    items: Optional[List[ShipmentItemResponse]] = []

    class Config:
        from_attributes = True

class OTPVerificationRequest(BaseModel):
    otp: str

class ShipmentStatusUpdate(BaseModel):
    status: ShipmentStatus
    notes: Optional[str] = None

class ShipmentAssignment(BaseModel):
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None

class ShipmentTrackingResponse(BaseModel):
    id: int
    shipment_id: int
    status: ShipmentStatus
    location: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    timestamp: datetime
    notes: Optional[str] = None
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True