from sqlalchemy import Column, Integer, String, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import UnitType

class InventoryCountItem(BaseModel):
    __tablename__ = 'inventory_count_items'
    
    inventory_count_id = Column(Integer, ForeignKey('inventory_counts.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    unit_type = Column(SQLEnum(UnitType), nullable=False)
    system_quantity = Column(Numeric(10, 2), nullable=False)
    counted_quantity = Column(Numeric(10, 2), nullable=False)
    variance_quantity = Column(Numeric(10, 2), nullable=False)
    unit_cost = Column(Numeric(10, 2))
    variance_value = Column(Numeric(12, 2))
    batch_number = Column(String(50))
    expiry_date = Column(Date)
    reason_id = Column(Integer, ForeignKey('inventory_mismatch_reasons.id'))
    remarks = Column(Text)
    
    # Relationships
    inventory_count = relationship("InventoryCount", back_populates="items")
    item = relationship("Item", back_populates="inventory_count_items")
    reason = relationship("InventoryMismatchReason", back_populates="inventory_count_items")