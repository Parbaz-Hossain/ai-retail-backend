from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import date as DateType, datetime
from app.models.shared.enums import OffdayType

class OffdayBase(BaseModel):
    employee_id: int
    year: int
    month: int
    offday_date: DateType
    offday_type: OffdayType = OffdayType.WEEKEND
    description: Optional[str] = None

class OffdayCreate(OffdayBase):
    @validator('month')
    def validate_month(cls, v):
        if not 1 <= v <= 12:
            raise ValueError('Month must be between 1 and 12')
        return v
    
    @validator('year')
    def validate_year(cls, v):
        if v < 2020:
            raise ValueError('Year must be 2020 or later')
        return v

class OffdayBulkCreate(BaseModel):
    employee_id: int
    year: int
    month: int
    offday_dates: List[DateType]
    offday_type: OffdayType = OffdayType.WEEKEND
    description: Optional[str] = None
    
    @validator('offday_dates')
    def validate_dates(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one offday date is required')
        if len(v) > 31:
            raise ValueError('Too many offday dates')
        return v

class OffdayUpdate(BaseModel):
    offday_date: Optional[DateType] = None
    offday_type: Optional[OffdayType] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class EmployeeInfo(BaseModel):
    id: int
    employee_id: str
    first_name: str
    last_name: str
    
    class Config:
        from_attributes = True

class OffdayResponse(OffdayBase):
    id: int
    employee: EmployeeInfo
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class OffdayListResponse(BaseModel):
    employee_id: int
    year: int
    month: int
    offdays: List[OffdayResponse]
    total_offdays: int