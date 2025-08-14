from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class ReorderRequestItem(BaseModel):
    __tablename__ = 'reorder_request_items'
    
    reorder_request_id = Column(Integer, ForeignKey('reorder_requests.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    current_stock = Column(Numeric(10, 2), nullable=False)
    requested_quantity = Column(Numeric(10, 2), nullable=False)
    approved_quantity = Column(Numeric(10, 2))
    estimated_unit_cost = Column(Numeric(10, 2))
    estimated_total_cost = Column(Numeric(12, 2))
    reason = Column(String(200))
    
    # Relationships
    reorder_request = relationship("ReorderRequest", back_populates="items")
    item = relationship("Item", back_populates="reorder_request_items")