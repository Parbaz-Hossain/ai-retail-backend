from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import SalaryPaymentStatus

class Salary(BaseModel):
    __tablename__ = 'salaries'
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    salary_month = Column(Date, nullable=False)  # First day of the month
    basic_salary = Column(Numeric(10, 2), nullable=False)
    housing_allowance = Column(Numeric(10, 2), default=0)
    transport_allowance = Column(Numeric(10, 2), default=0)
    overtime_amount = Column(Numeric(10, 2), default=0)
    bonus = Column(Numeric(10, 2), default=0)
    total_deductions = Column(Numeric(10, 2), default=0)
    late_deductions = Column(Numeric(10, 2), default=0)
    absent_deductions = Column(Numeric(10, 2), default=0)
    other_deductions = Column(Numeric(10, 2), default=0)
    gross_salary = Column(Numeric(10, 2), nullable=False)
    net_salary = Column(Numeric(10, 2), nullable=False)
    working_days = Column(Integer)
    present_days = Column(Integer)
    absent_days = Column(Integer)
    late_days = Column(Integer)
    payment_status = Column(SQLEnum(SalaryPaymentStatus), default=SalaryPaymentStatus.UNPAID)
    payment_date = Column(DateTime(timezone=True))
    payment_method = Column(String(50))
    payment_reference = Column(String(100))
    generated_by = Column(Integer)  # User ID who generated
    approved_by = Column(Integer)  # User ID who approved
    
    # Relationships
    employee = relationship("Employee", back_populates="salaries")
    deduction_details = relationship("SalaryDeduction", back_populates="salary")