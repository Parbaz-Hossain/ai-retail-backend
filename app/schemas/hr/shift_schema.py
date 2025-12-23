from app.models.shared.enums import DayOfWeek
from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import time, date, datetime
from enum import Enum

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

class BulkUserShiftCreate(BaseModel):
    """Schema for assigning shifts to multiple employees at once"""
    employee_ids: List[int]
    shift_type_id: int
    effective_date: date
    end_date: Optional[date] = None
    deduction_amount: Optional[float] = None
    
    @validator('employee_ids')
    def validate_employee_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one employee ID is required')
        if len(v) != len(set(v)):
            raise ValueError('Duplicate employee IDs found')
        return v

class EmployeeShiftAndOffday(BaseModel):
    """Single employee shift and offday assignment"""
    employee_id: int
    shift_type_id: int
    off_day: DayOfWeek
    
    @validator('employee_id')
    def validate_employee_id(cls, v):
        if v <= 0:
            raise ValueError('Employee ID must be positive')
        return v
    
    @validator('shift_type_id')
    def validate_shift_type_id(cls, v):
        if v <= 0:
            raise ValueError('Shift type ID must be positive')
        return v

class BulkShiftAndOffdayAssignment(BaseModel):
    """Schema for assigning shifts and offdays to multiple employees"""
    employees: List[EmployeeShiftAndOffday]
    year: Optional[int] = None  # If not provided, use current year
    month: Optional[int] = None  # If not provided, use current month
    
    @validator('employees')
    def validate_employees(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one employee assignment is required')
        
        # Check for duplicate employee IDs
        employee_ids = [emp.employee_id for emp in v]
        if len(employee_ids) != len(set(employee_ids)):
            raise ValueError('Duplicate employee IDs found in the list')
        
        return v
    
    @validator('month')
    def validate_month(cls, v):
        if v is not None and not (1 <= v <= 12):
            raise ValueError('Month must be between 1 and 12')
        return v
    
    @validator('year')
    def validate_year(cls, v):
        if v is not None and v < 2020:
            raise ValueError('Year must be 2020 or later')
        return v

class EmployeeAssignmentResult(BaseModel):
    """Result for a single employee assignment"""
    employee_id: int
    employee_code: Optional[str] = None
    employee_name: Optional[str] = None
    status: str  # "success" or "failed"
    shift_assigned: bool = False
    offdays_created: int = 0
    error: Optional[str] = None

class BulkShiftAndOffdayResult(BaseModel):
    """Result of bulk shift and offday assignment operation"""
    total_requested: int
    successful: int
    failed: int
    year: int
    month: int
    effective_date: date
    end_date: date
    results: List[EmployeeAssignmentResult]

class BulkShiftAssignmentResult(BaseModel):
    """Result of bulk shift assignment operation"""
    total_requested: int
    successful: int
    failed: int
    results: List[dict]

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