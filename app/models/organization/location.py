from sqlalchemy import Column, String, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.base import BaseModel

class Location(BaseModel):
    __tablename__ = 'locations'
    
    name = Column(String(100), nullable=False)
    location_type = Column(SQLEnum("BRANCH", "WAREHOUSE", name="location_type"), nullable=False)
    address = Column(Text)
    city = Column(String(50))
    state = Column(String(50))
    postal_code = Column(String(20))
    country = Column(String(50), default="Bangladesh")
    phone = Column(String(20))
    email = Column(String(100))
    
    # Relationships
    employees = relationship("Employee", back_populates="location")
    stock_levels = relationship("StockLevel", back_populates="location")
    stock_movements = relationship("StockMovement", back_populates="location")
    reorder_requests = relationship("ReorderRequest", back_populates="location")
    transfers_from = relationship("Transfer", foreign_keys="Transfer.from_location_id", back_populates="from_location")
    transfers_to = relationship("Transfer", foreign_keys="Transfer.to_location_id", back_populates="to_location")
    inventory_counts = relationship("InventoryCount", back_populates="location")
    shipments_from = relationship("Shipment", foreign_keys="Shipment.from_location_id", back_populates="from_location")
    shipments_to = relationship("Shipment", foreign_keys="Shipment.to_location_id", back_populates="to_location")
