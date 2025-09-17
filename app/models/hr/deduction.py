from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date
from sqlalchemy.orm import relationship
from app.db.base import BaseModel
from app.models.shared.enums import DeductionStatus

class DeductionType(BaseModel):
    __tablename__ = 'deduction_types'
    
    name = Column(String(100), nullable=False, unique=True) 
    description = Column(Text)
    is_auto_calculated = Column(Boolean, default=False)  # True for late/absent, False for manual penalties
    default_amount = Column(Numeric(10, 2), default=0) 
    is_active = Column(Boolean, default=True)
    
    # Relationships
    employee_deductions = relationship("EmployeeDeduction", back_populates="deduction_type")

class EmployeeDeduction(BaseModel):
    __tablename__ = 'employee_deductions'
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    deduction_type_id = Column(Integer, ForeignKey('deduction_types.id'), nullable=False)
    total_amount = Column(Numeric(10, 2), default=0)  
    paid_amount = Column(Numeric(10, 2), default=0) 
    remaining_amount = Column(Numeric(10, 2), default=0)  
    monthly_deduction_limit = Column(Numeric(10, 2), default=0)  
    effective_from = Column(Date, nullable=False)  
    effective_to = Column(Date)  
    status = Column(SQLEnum(DeductionStatus), default=DeductionStatus.ACTIVE)
    description = Column(Text)  
    created_by = Column(Integer)  
    
    # Relationships
    employee = relationship("Employee", back_populates="deductions")
    deduction_type = relationship("DeductionType", back_populates="employee_deductions")
    salary_deductions = relationship("SalaryDeduction", back_populates="employee_deduction")

class SalaryDeduction(BaseModel):
    __tablename__ = 'salary_deductions'
    
    salary_id = Column(Integer, ForeignKey('salaries.id'), nullable=False)
    employee_deduction_id = Column(Integer, ForeignKey('employee_deductions.id'), nullable=False)
    deduction_type_id = Column(Integer, ForeignKey('deduction_types.id'), nullable=False)
    deducted_amount = Column(Numeric(10, 2), nullable=False)
    salary_month = Column(Date, nullable=False)
    
    # Relationships
    salary = relationship("Salary", back_populates="deduction_details")
    employee_deduction = relationship("EmployeeDeduction", back_populates="salary_deductions")
    deduction_type = relationship("DeductionType")