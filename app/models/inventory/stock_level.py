from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class StockLevel(BaseModel):
    __tablename__ = 'stock_levels'
    
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    current_stock = Column(Numeric(10, 2), nullable=False, default=0)
    reserved_stock = Column(Numeric(10, 2), default=0)
    available_stock = Column(Numeric(10, 2), nullable=False, default=0)
    par_level_min = Column(Numeric(10, 2), default=0)
    par_level_max = Column(Numeric(10, 2), default=0)
    
    # Composite unique constraint
    __table_args__ = (
        {"extend_existing": True},
    )

    # Relationships
    item = relationship("Item", back_populates="stock_levels")
    location = relationship("Location", back_populates="stock_levels")