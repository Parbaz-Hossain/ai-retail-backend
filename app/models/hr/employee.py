from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class Employee(BaseModel):
    __tablename__ = 'employees'
    
    employee_id = Column(String(20), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False)  # Reference to User from auth system
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20))
    date_of_birth = Column(Date)
    hire_date = Column(Date, nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'))
    location_id = Column(Integer, ForeignKey('locations.id'))
    position = Column(String(100))
    basic_salary = Column(Numeric(10, 2))
    housing_allowance = Column(Numeric(10, 2), default=0)
    transport_allowance = Column(Numeric(10, 2), default=0)
    is_manager = Column(Boolean, default=False)
    bio_id = Column(String(50))  # Biometric ID
    profile_image = Column(String(255))
    emergency_contact = Column(String(100))
    emergency_phone = Column(String(20))
    address = Column(Text)
    is_fingerprint_registered = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    department = relationship("Department", back_populates="employees")
    location = relationship("Location", back_populates="employees")
    salaries = relationship("Salary", back_populates="employee")
    attendances = relationship("Attendance", back_populates="employee")
    user_shifts = relationship("UserShift", back_populates="employee")