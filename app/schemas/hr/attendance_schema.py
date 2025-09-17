from pydantic import BaseModel, validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from app.models.shared.enums import AttendanceStatus

class AttendanceBase(BaseModel):
    employee_id: int
    attendance_date: date
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

class AttendanceCreate(AttendanceBase):
    bio_check_in: Optional[bool] = False
    bio_check_out: Optional[bool] = False
    remarks: Optional[str] = None

class AttendanceUpdate(BaseModel):
    check_out_time: Optional[datetime] = None
    bio_check_out: Optional[bool] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    remarks: Optional[str] = None
    status: Optional[AttendanceStatus] = None

class EmployeeInfo(BaseModel):
    id: int
    employee_id: str
    first_name: str
    last_name: str
    
    class Config:
        from_attributes = True

class AttendanceResponse(AttendanceBase):
    id: int
    employee: EmployeeInfo
    total_hours: Optional[Decimal] = None
    overtime_hours: Optional[Decimal] = None
    late_minutes: Optional[int] = None
    early_leave_minutes: Optional[int] = None
    status: AttendanceStatus
    bio_check_in: Optional[bool] = None
    bio_check_out: Optional[bool] = None
    remarks: Optional[str] = None
    is_holiday: Optional[bool] = None
    is_weekend: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
