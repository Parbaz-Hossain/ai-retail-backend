from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class UserShift(BaseModel):
    __tablename__ = 'user_shifts'
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    shift_type_id = Column(Integer, ForeignKey('shift_types.id'), nullable=False)
    effective_date = Column(Date, nullable=False)
    end_date = Column(Date)  # NULL means current
    is_active = Column(Boolean, default=True)
    
    # Relationships
    employee = relationship("Employee", back_populates="user_shifts")
    shift_type = relationship("ShiftType", back_populates="user_shifts")