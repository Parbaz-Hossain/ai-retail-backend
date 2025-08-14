from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class ItemSupplier(BaseModel):
    __tablename__ = 'item_suppliers'
    
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    supplier_item_code = Column(String(100))
    unit_cost = Column(Numeric(10, 2), nullable=False)
    minimum_order_quantity = Column(Numeric(10, 2), default=1)
    lead_time_days = Column(Integer, default=0)
    is_preferred = Column(Boolean, default=False)
    
    # Relationships
    item = relationship("Item", back_populates="item_suppliers")
    supplier = relationship("Supplier", back_populates="item_suppliers")