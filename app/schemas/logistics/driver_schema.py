from pydantic import BaseModel, validator
from typing import Optional
from datetime import date, datetime
from app.schemas.hr.employee_schema import EmployeeResponse

class DriverBase(BaseModel):
    license_number: str
    license_expiry: Optional[date] = None
    license_type: Optional[str] = None
    experience_years: Optional[int] = None
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    is_available: bool = True
    is_active: bool = True

class DriverCreate(DriverBase):
    employee_id: int

class DriverUpdate(BaseModel):
    license_number: Optional[str] = None
    license_expiry: Optional[date] = None
    license_type: Optional[str] = None
    experience_years: Optional[int] = None
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    is_available: Optional[bool] = None
    is_active: Optional[bool] = None

class DriverResponse(DriverBase):
    id: int
    employee_id: int
    employee: Optional[EmployeeResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True