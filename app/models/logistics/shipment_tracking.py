from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import ShipmentStatus

class ShipmentTracking(BaseModel):
    __tablename__ = 'shipment_tracking'
    
    shipment_id = Column(Integer, ForeignKey('shipments.id'), nullable=False)
    status = Column(SQLEnum(ShipmentStatus), nullable=False)
    location = Column(String(200))
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    timestamp = Column(DateTime(timezone=True), nullable=False)
    notes = Column(Text)
    updated_by = Column(Integer)  # User ID
    
    # Relationships
    shipment = relationship("Shipment", back_populates="tracking_updates")