from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

class EmployeeInfo(BaseModel):
    id: int
    employee_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    
    class Config:
        from_attributes = True

class TicketBase(BaseModel):
    ticket_no: str
    employee_id: int
    ticket_type: str
    deduction_amount: Optional[Decimal] = None

class TicketCreate(BaseModel):
    employee_id: int
    ticket_type: str  # "LATE", "ABSENT", "EARLY_LEAVE", etc.
    deduction_amount: Optional[Decimal] = None

class TicketResponse(TicketBase):
    id: int
    employee: EmployeeInfo
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class EmployeeTicketSummary(BaseModel):
    """Summary of tickets for an employee in the list view"""
    employee_id: int
    employee_info: EmployeeInfo
    total_tickets: Optional[int] = None
    total_deduction: Optional[Decimal] = None
    late_tickets: Optional[int] = None
    absent_tickets: Optional[int] = None
    early_leave_tickets: Optional[int] = None
    other_tickets: Optional[int] = None
    latest_ticket_date: Optional[datetime] = None
    tickets: List[TicketResponse]  # Recent tickets for preview
    
    class Config:
        from_attributes = True