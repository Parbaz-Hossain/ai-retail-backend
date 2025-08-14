from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class UserShift(BaseModel):
    __tablename__ = 'user_shifts'
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    shift_type_id = Column(Integer, ForeignKey('shift_types.id'), nullable=False)
    effective_date = Column(Date, nullable=False)
    end_date = Column(Date)  # NULL means current
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    employee = relationship("Employee", back_populates="user_shifts")
    shift_type = relationship("ShiftType", back_populates="user_shifts")