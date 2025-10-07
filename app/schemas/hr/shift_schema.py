from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import time, date, datetime

class ShiftTypeBase(BaseModel):
    name: str
    start_time: time
    end_time: time
    break_duration_minutes: int = 0
    late_grace_minutes: int = 15

class ShiftTypeCreate(ShiftTypeBase):
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Shift name must be at least 2 characters')
        return v.strip()

class ShiftTypeUpdate(BaseModel):
    name: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    break_duration_minutes: Optional[int] = None
    late_grace_minutes: Optional[int] = None
    is_active: Optional[bool] = None

class ShiftTypeResponse(ShiftTypeBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class UserShiftBase(BaseModel):
    employee_id: int
    shift_type_id: int
    effective_date: date
    end_date: Optional[date] = None
    deduction_amount: Optional[float] = None

class UserShiftCreate(UserShiftBase):
    pass

class UserShiftUpdate(BaseModel):
    shift_type_id: Optional[int] = None
    effective_date: Optional[date] = None
    end_date: Optional[date] = None
    deduction_amount: Optional[float] = None
    is_active: Optional[bool] = None

class UserShiftResponse(UserShiftBase):
    id: int
    shift_type: ShiftTypeResponse
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class EmployeeShiftSummary(BaseModel):
    """Summary for displaying in shift list"""
    employee_id: int
    employee_code: str
    employee_name: str
    department: Optional[str] = None
    current_shift: Optional[UserShiftResponse] = None
    total_shift_changes: int
    latest_effective_date: Optional[date] = None
    
    class Config:
        from_attributes = True

class EmployeeShiftDetail(BaseModel):
    """Detailed view with all shifts for an employee"""
    employee_id: int
    employee_code: str
    employee_name: str
    department: Optional[str] = None
    current_shift: Optional[UserShiftResponse] = None
    shift_history: List[UserShiftResponse] = []
    total_shifts: int
    
    class Config:
        from_attributes = True