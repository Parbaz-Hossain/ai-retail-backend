from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from app.models.shared.enums import DeductionStatus

# Deduction Type Schemas
class DeductionTypeBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_auto_calculated: bool = False
    default_amount: Decimal = Decimal('0')
    is_active: bool = True

class DeductionTypeCreate(DeductionTypeBase):
    pass

class DeductionTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_auto_calculated: Optional[bool] = None
    default_amount: Optional[Decimal] = None
    is_active: Optional[bool] = None

class DeductionTypeResponse(DeductionTypeBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Employee Deduction Schemas
class EmployeeDeductionBase(BaseModel):
    employee_id: int
    deduction_type_id: int
    total_amount: Optional[Decimal] = None
    monthly_deduction_limit: Optional[Decimal] = None
    effective_from: date
    effective_to: Optional[date] = None
    description: Optional[str] = None

class EmployeeDeductionCreate(EmployeeDeductionBase):    
    pass

class EmployeeDeductionUpdate(BaseModel):
    total_amount: Optional[Decimal] = None
    monthly_deduction_limit: Optional[Decimal] = None
    effective_to: Optional[date] = None
    status: Optional[DeductionStatus] = None
    description: Optional[str] = None

class EmployeeInfo(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None

class EmployeeDeductionResponse(EmployeeDeductionBase):
    id: int
    paid_amount: Optional[Decimal] = None
    remaining_amount: Optional[Decimal] = None
    status: DeductionStatus
    created_by: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Related data
    deduction_type: Optional[DeductionTypeResponse] = None
    employee : Optional[EmployeeInfo] = None  
    
    class Config:
        from_attributes = True

# Salary Deduction Schemas
class SalaryDeductionResponse(BaseModel):
    id: int
    employee_deduction_id: int
    deduction_type_id: int
    deducted_amount: Decimal
    salary_month: date
    
    # Related data
    deduction_type: Optional[DeductionTypeResponse] = None
    
    class Config:
        from_attributes = True

# Bulk Operations
class BulkDeductionCreate(BaseModel):
    employee_ids: List[int]
    deduction_type_id: int
    total_amount: Optional[Decimal] = None
    monthly_deduction_limit: Optional[Decimal] = None
    effective_from: date
    effective_to: Optional[date] = None
    description: Optional[str] = None
