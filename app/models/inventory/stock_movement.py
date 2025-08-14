from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import StockMovementType

class StockMovement(BaseModel):
    __tablename__ = 'stock_movements'
    
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    movement_type = Column(SQLEnum(StockMovementType), nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False)
    unit_cost = Column(Numeric(10, 2))
    total_cost = Column(Numeric(10, 2))
    reference_type = Column(String(50))  # PO, TRANSFER, ADJUSTMENT, etc.
    reference_id = Column(Integer)
    batch_number = Column(String(50))
    expiry_date = Column(Date)
    remarks = Column(Text)
    performed_by = Column(Integer)  # User ID
    movement_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    item = relationship("Item", back_populates="stock_movements")
    location = relationship("Location", back_populates="stock_movements")