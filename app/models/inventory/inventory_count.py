from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class InventoryCount(BaseModel):
    __tablename__ = 'inventory_counts'
    
    count_number = Column(String(50), unique=True, nullable=False)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    count_date = Column(Date, nullable=False)
    count_type = Column(String(20), default="FULL")  # FULL, PARTIAL, CYCLE
    status = Column(String(20), default="IN_PROGRESS")  # IN_PROGRESS, COMPLETED, CANCELLED
    conducted_by = Column(Integer)  # User ID
    verified_by = Column(Integer)  # User ID
    notes = Column(Text)
    
    # Relationships
    location = relationship("Location", back_populates="inventory_counts")
    items = relationship("InventoryCountItem", back_populates="inventory_count")
