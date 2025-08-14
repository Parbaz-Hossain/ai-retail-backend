from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class Driver(BaseModel):
    __tablename__ = 'drivers'
    
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    license_number = Column(String(50), unique=True, nullable=False)
    license_expiry = Column(Date)
    license_type = Column(String(20))  # A, B, C, D, etc.
    experience_years = Column(Integer)
    phone = Column(String(20))
    emergency_contact = Column(String(100))
    emergency_phone = Column(String(20))
    is_available = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    employee = relationship("Employee")
    shipments = relationship("Shipment", back_populates="driver")
