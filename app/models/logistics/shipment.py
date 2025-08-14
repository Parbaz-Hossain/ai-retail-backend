from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import ShipmentStatus

class Shipment(BaseModel):
    __tablename__ = 'shipments'
    
    shipment_number = Column(String(50), unique=True, nullable=False)
    from_location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    to_location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    driver_id = Column(Integer, ForeignKey('drivers.id'))
    vehicle_id = Column(Integer, ForeignKey('vehicles.id'))
    reference_type = Column(String(50))  # TRANSFER, PURCHASE_ORDER, DELIVERY
    reference_id = Column(Integer)
    shipment_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date)
    actual_delivery_date = Column(DateTime(timezone=True))
    status = Column(SQLEnum(ShipmentStatus), default=ShipmentStatus.READY_FOR_PICKUP)
    pickup_otp = Column(String(6))
    delivery_otp = Column(String(6))
    pickup_otp_verified = Column(Boolean, default=False)
    delivery_otp_verified = Column(Boolean, default=False)
    pickup_time = Column(DateTime(timezone=True))
    delivery_time = Column(DateTime(timezone=True))
    distance_km = Column(Numeric(8, 2))
    fuel_cost = Column(Numeric(10, 2))
    total_weight = Column(Numeric(10, 2))
    total_volume = Column(Numeric(10, 2))
    sender_signature = Column(String(255))  # File path
    receiver_signature = Column(String(255))  # File path
    notes = Column(Text)
    created_by = Column(Integer)  # User ID
    
    # Relationships
    from_location = relationship("Location", foreign_keys=[from_location_id], back_populates="shipments_from")
    to_location = relationship("Location", foreign_keys=[to_location_id], back_populates="shipments_to")
    driver = relationship("Driver", back_populates="shipments")
    vehicle = relationship("Vehicle", back_populates="shipments")
    items = relationship("ShipmentItem", back_populates="shipment")
    tracking_updates = relationship("ShipmentTracking", back_populates="shipment")