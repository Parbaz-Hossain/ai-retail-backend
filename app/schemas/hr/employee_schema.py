from pydantic import BaseModel, ConfigDict, validator, EmailStr
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

class EmployeeBase(BaseModel):
    user_id: int
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    hire_date: date
    department_id: int
    location_id: int
    position: Optional[str] = None
    basic_salary: Optional[Decimal] = None
    housing_allowance: Optional[Decimal] = None
    transport_allowance: Optional[Decimal] = None
    is_manager: Optional[bool] = False
    bio_id: Optional[str] = None
    profile_image: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    address: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class EmployeeCreate(EmployeeBase):
    @validator('first_name', 'last_name')
    def validate_names(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Name must be at least 2 characters')
        return v.strip().title()
    
    @validator('hire_date')
    def validate_hire_date(cls, v):
        if v > date.today():
            raise ValueError('Hire date cannot be in the future')
        return v

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    department_id: Optional[int] = None
    location_id: Optional[int] = None
    position: Optional[str] = None
    basic_salary: Optional[Decimal] = None
    housing_allowance: Optional[Decimal] = None
    transport_allowance: Optional[Decimal] = None
    is_manager: Optional[bool] = None
    bio_id: Optional[str] = None
    profile_image: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None

class DepartmentInfo(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)

class LocationInfo(BaseModel):
    id: int
    name: str
    location_type: str
    city: Optional[str]
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)
    
class EmployeeResponse(EmployeeBase):
    id: int
    employee_id: str
    is_fingerprint_registered: Optional[bool] = False
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    department: Optional[DepartmentInfo]
    location: Optional[LocationInfo]    
    
    model_config = ConfigDict(from_attributes=True)

