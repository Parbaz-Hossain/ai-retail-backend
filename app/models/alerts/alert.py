from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class Alert(BaseModel):
    __tablename__ = 'alerts'
    
    alert_type = Column(String(50), nullable=False)  # LOW_STOCK, EXPIRY, OVERDUE, etc.
    severity = Column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    entity_type = Column(String(50))  # ITEM, PURCHASE_ORDER, EMPLOYEE, etc.
    entity_id = Column(Integer)
    is_read = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    assigned_to = Column(Integer)  # User ID
    resolved_by = Column(Integer)  # User ID
    resolved_at = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)