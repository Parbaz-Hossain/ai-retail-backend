from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class Vehicle(BaseModel):
    __tablename__ = 'vehicles'
    
    vehicle_number = Column(String(20), unique=True, nullable=False)
    vehicle_type = Column(String(50))  # Truck, Van, Bike, etc.
    model = Column(String(100))
    year = Column(Integer)
    capacity_weight = Column(Numeric(8, 2))  # in KG
    capacity_volume = Column(Numeric(8, 2))  # in cubic meters
    fuel_type = Column(String(20))  # Petrol, Diesel, Electric, etc.
    registration_expiry = Column(Date)
    insurance_expiry = Column(Date)
    last_maintenance_date = Column(Date)
    next_maintenance_date = Column(Date)
    current_mileage = Column(Integer)
    is_available = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    shipments = relationship("Shipment", back_populates="vehicle")