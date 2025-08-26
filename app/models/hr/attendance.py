from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import AttendanceStatus

class Attendance(BaseModel):
    __tablename__ = 'attendances'
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    attendance_date = Column(Date, nullable=False)
    check_in_time = Column(DateTime(timezone=True))
    check_out_time = Column(DateTime(timezone=True))
    total_hours = Column(Numeric(4, 2))
    overtime_hours = Column(Numeric(4, 2), default=0)
    late_minutes = Column(Integer, default=0)
    early_leave_minutes = Column(Integer, default=0)
    status = Column(SQLEnum(AttendanceStatus), nullable=False)
    bio_check_in = Column(Boolean, default=False)
    bio_check_out = Column(Boolean, default=False)
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    remarks = Column(Text)
    is_holiday = Column(Boolean, default=False)
    
    # Relationships
    employee = relationship("Employee", back_populates="attendances")