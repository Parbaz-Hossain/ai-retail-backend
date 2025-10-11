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

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel
from enum import Enum


class SalaryPaymentStatus(str, Enum):
    PENDING = "Pending"
    PAID = "Paid"
    FAILED = "Failed"


class SalaryResponse(BaseModel):
    id: int
    basic_salary: Optional[Decimal] = None
    housing_allowance: Optional[Decimal] = None
    transport_allowance: Optional[Decimal] = None
    overtime_amount: Optional[Decimal] = None
    bonus: Optional[Decimal] = None
    total_deductions: Optional[Decimal] = None
    late_deductions: Optional[Decimal] = None
    absent_deductions: Optional[Decimal] = None
    other_deductions: Optional[Decimal] = None
    gross_salary: Optional[Decimal] = None
    net_salary: Optional[Decimal] = None  # <-- negative allowed
    working_days: Optional[int] = None
    present_days: Optional[int] = None
    absent_days: Optional[int] = None
    late_days: Optional[int] = None
    payment_status: Optional[SalaryPaymentStatus] = None
    payment_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    generated_by: Optional[int] = None
    approved_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
