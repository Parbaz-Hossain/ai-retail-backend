from sqlalchemy import Column, Integer, String, Boolean, Text
from sqlalchemy.orm import relationship
from app.db.base import BaseModel

class InventoryMismatchReason(BaseModel):
    __tablename__ = 'inventory_mismatch_reasons'
    
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)

    # Relationships
    inventory_count_items = relationship("InventoryCountItem", back_populates="reason")