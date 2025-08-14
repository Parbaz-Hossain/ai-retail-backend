from pydantic import BaseModel, validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from app.models.shared.enums import SalaryPaymentStatus

class SalaryBase(BaseModel):
    employee_id: int
    salary_month: date

class SalaryCreate(SalaryBase):
    pass

class SalaryUpdate(BaseModel):
    bonus: Optional[Decimal] = None
    other_deductions: Optional[Decimal] = None
    payment_status: Optional[SalaryPaymentStatus] = None

class SalaryPaymentUpdate(BaseModel):
    payment_date: datetime
    payment_method: str
    payment_reference: str

class SalaryResponse(SalaryBase):
    id: int
    basic_salary: Decimal
    housing_allowance: Decimal
    transport_allowance: Decimal
    overtime_amount: Decimal
    bonus: Decimal
    total_deductions: Decimal
    late_deductions: Decimal
    absent_deductions: Decimal
    other_deductions: Decimal
    gross_salary: Decimal
    net_salary: Decimal
    working_days: int
    present_days: int
    absent_days: int
    late_days: int
    payment_status: SalaryPaymentStatus
    payment_date: Optional[datetime]
    payment_method: Optional[str]
    payment_reference: Optional[str]
    generated_by: int
    approved_by: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True