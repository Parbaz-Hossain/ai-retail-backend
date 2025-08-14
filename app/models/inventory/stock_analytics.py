from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class StockAnalytics(BaseModel):
    __tablename__ = 'stock_analytics'
    
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    date = Column(Date, nullable=False)
    opening_stock = Column(Numeric(10, 2), default=0)
    closing_stock = Column(Numeric(10, 2), default=0)
    total_inbound = Column(Numeric(10, 2), default=0)
    total_outbound = Column(Numeric(10, 2), default=0)
    total_transfers_in = Column(Numeric(10, 2), default=0)
    total_transfers_out = Column(Numeric(10, 2), default=0)
    total_adjustments = Column(Numeric(10, 2), default=0)
    total_waste = Column(Numeric(10, 2), default=0)
    turnover_rate = Column(Numeric(5, 2))
    days_on_hand = Column(Integer)
    stock_value = Column(Numeric(12, 2))
    
    # Relationships
    item = relationship("Item")
    location = relationship("Location")