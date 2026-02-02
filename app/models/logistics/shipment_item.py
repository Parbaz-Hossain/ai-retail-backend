from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import UnitType

class ShipmentItem(BaseModel):
    __tablename__ = 'shipment_items'
    
    shipment_id = Column(Integer, ForeignKey('shipments.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    unit_type = Column(SQLEnum(UnitType), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    delivered_quantity = Column(Numeric(10, 2))
    weight = Column(Numeric(8, 2))
    volume = Column(Numeric(8, 2))
    batch_number = Column(String(50))
    expiry_date = Column(Date)
    packaging_type = Column(String(50))
    special_handling = Column(String(100))
    
    # Relationships
    shipment = relationship("Shipment", back_populates="items")
    item = relationship("Item")