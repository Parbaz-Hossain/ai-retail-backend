from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class ShiftType(BaseModel):
    __tablename__ = 'shift_types'
    
    name = Column(String(50), nullable=False, unique=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    break_duration_minutes = Column(Integer, default=0)
    late_grace_minutes = Column(Integer, default=15)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user_shifts = relationship("UserShift", back_populates="shift_type")