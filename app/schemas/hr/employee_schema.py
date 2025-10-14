from fastapi import Form
from pydantic import BaseModel, ConfigDict, validator, EmailStr
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    user_id: Optional[int] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    hire_date: date
    department_id: Optional[int] = None
    location_id: Optional[int] = None
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
    
class EmployeeCreateForm:
    def __init__(
        self,
        first_name: str = Form(...),
        last_name: str = Form(...),
        email: str = Form(...),
        user_id: Optional[int] = Form(None),
        phone: Optional[str] = Form(None),
        date_of_birth: Optional[date] = Form(None),
        hire_date: date = Form(...),
        department_id: int = Form(...),
        location_id: int = Form(...),
        position: Optional[str] = Form(None),
        basic_salary: Optional[Decimal] = Form(None),
        housing_allowance: Optional[Decimal] = Form(0),
        transport_allowance: Optional[Decimal] = Form(0),
        is_manager: bool = Form(False),
        emergency_contact: Optional[str] = Form(None),
        emergency_phone: Optional[str] = Form(None),
        address: Optional[str] = Form(None)
    ):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.user_id = user_id
        self.phone = phone
        self.date_of_birth = date_of_birth
        self.hire_date = hire_date
        self.department_id = department_id
        self.location_id = location_id
        self.position = position
        self.basic_salary = basic_salary
        self.housing_allowance = housing_allowance
        self.transport_allowance = transport_allowance
        self.is_manager = is_manager
        self.emergency_contact = emergency_contact
        self.emergency_phone = emergency_phone
        self.address = address
    
    def to_employee_create(self) -> EmployeeCreate:
        """Convert form data to EmployeeCreate schema"""
        return EmployeeCreate(
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
            user_id=self.user_id,
            phone=self.phone,
            date_of_birth=self.date_of_birth,
            hire_date=self.hire_date,
            department_id=self.department_id,
            location_id=self.location_id,
            position=self.position,
            basic_salary=self.basic_salary,
            housing_allowance=self.housing_allowance,
            transport_allowance=self.transport_allowance,
            is_manager=self.is_manager,
            emergency_contact=self.emergency_contact,
            emergency_phone=self.emergency_phone,
            address=self.address
        )

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    user_id: Optional[int] = None
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

class EmployeeUpdateForm:
    def __init__(
        self,
        first_name: Optional[str] = Form(None),
        last_name: Optional[str] = Form(None),
        user_id: Optional[int] = Form(None),
        email: Optional[str] = Form(None),
        phone: Optional[str] = Form(None),
        date_of_birth: Optional[date] = Form(None),
        department_id: Optional[int] = Form(None),
        location_id: Optional[int] = Form(None),
        position: Optional[str] = Form(None),
        basic_salary: Optional[Decimal] = Form(None),
        housing_allowance: Optional[Decimal] = Form(None),
        transport_allowance: Optional[Decimal] = Form(None),
        is_manager: Optional[bool] = Form(None),
        emergency_contact: Optional[str] = Form(None),
        emergency_phone: Optional[str] = Form(None),
        address: Optional[str] = Form(None),
        is_active: Optional[bool] = Form(None)
    ):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.user_id = user_id
        self.phone = phone
        self.date_of_birth = date_of_birth
        self.department_id = department_id
        self.location_id = location_id
        self.position = position
        self.basic_salary = basic_salary
        self.housing_allowance = housing_allowance
        self.transport_allowance = transport_allowance
        self.is_manager = is_manager
        self.emergency_contact = emergency_contact
        self.emergency_phone = emergency_phone
        self.address = address
        self.is_active = is_active
    
    def to_employee_update(self) -> EmployeeUpdate:
        """Convert form data to EmployeeUpdate schema"""
        return EmployeeUpdate(
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
            user_id=self.user_id,
            phone=self.phone,
            date_of_birth=self.date_of_birth,
            department_id=self.department_id,
            location_id=self.location_id,
            position=self.position,
            basic_salary=self.basic_salary,
            housing_allowance=self.housing_allowance,
            transport_allowance=self.transport_allowance,
            is_manager=self.is_manager,
            emergency_contact=self.emergency_contact,
            emergency_phone=self.emergency_phone,
            address=self.address,
            is_active=self.is_active
        )

class DepartmentInfo(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)

class LocationInfo(BaseModel):
    id: int
    name: str
    location_type: str
    city: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)
    
class EmployeeResponse(EmployeeBase):
    id: int
    employee_id: str
    is_fingerprint_registered: Optional[bool] = False
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    department: Optional[DepartmentInfo] = None
    location: Optional[LocationInfo] = None    
    
    model_config = ConfigDict(from_attributes=True)

