from sqlalchemy import Boolean, Column, Numeric, String, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Uuid
from uuid import uuid4
from app.db.base import BaseModel

class Location(BaseModel):
    __tablename__ = 'locations'
    
    foodics_guid = Column(Uuid(as_uuid=True), unique=True, nullable=True)  # Foodics branch ID
    name = Column(String(100), nullable=False)
    location_type = Column(SQLEnum('WAREHOUSE', 'BRANCH', 'CENTRAL_KITCHEN', name='location_type', create_type=False), nullable=False)
    address = Column(Text)
    city = Column(String(50))
    state = Column(String(50))
    postal_code = Column(String(20))
    country = Column(String(50), default="Bangladesh")
    phone = Column(String(20))
    email = Column(String(100))
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    employees = relationship("Employee", back_populates="location")
    stock_levels = relationship("StockLevel", back_populates="location")
    stock_movements = relationship("StockMovement", back_populates="location")
    reorder_requests = relationship("ReorderRequest", foreign_keys="ReorderRequest.location_id", back_populates="location")
    incoming_reorder_requests = relationship("ReorderRequest", foreign_keys="ReorderRequest.to_location_id", back_populates="to_location")
    transfers_from = relationship("Transfer", foreign_keys="Transfer.from_location_id", back_populates="from_location")
    transfers_to = relationship("Transfer", foreign_keys="Transfer.to_location_id", back_populates="to_location")
    inventory_counts = relationship("InventoryCount", back_populates="location")
    shipments_from = relationship("Shipment", foreign_keys="Shipment.from_location_id", back_populates="from_location")
    shipments_to = relationship("Shipment", foreign_keys="Shipment.to_location_id", back_populates="to_location")
    orders = relationship("Order", back_populates="location")
