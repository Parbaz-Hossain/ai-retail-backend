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

class AttendanceCreate(AttendanceBase):
    bio_check_in: Optional[bool] = False
    bio_check_out: Optional[bool] = False
    remarks: Optional[str] = None

class AttendanceUpdate(BaseModel):
    check_out_time: Optional[datetime] = None
    bio_check_out: Optional[bool] = None
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
    total_hours: Optional[Decimal]
    overtime_hours: Optional[Decimal]
    late_minutes: int
    early_leave_minutes: int
    status: AttendanceStatus
    bio_check_in: bool
    bio_check_out: bool
    remarks: Optional[str]
    is_holiday: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
