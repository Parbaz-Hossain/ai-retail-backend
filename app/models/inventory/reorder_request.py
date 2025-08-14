from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import ReorderRequestStatus

class ReorderRequest(BaseModel):
    __tablename__ = 'reorder_requests'
    
    request_number = Column(String(50), unique=True, nullable=False)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    request_date = Column(Date, nullable=False)
    required_date = Column(Date)
    status = Column(SQLEnum(ReorderRequestStatus), default=ReorderRequestStatus.PENDING)
    priority = Column(String(20), default="NORMAL")  # LOW, NORMAL, HIGH, URGENT
    total_estimated_cost = Column(Numeric(12, 2))
    requested_by = Column(Integer)  # User ID
    approved_by = Column(Integer)  # User ID
    approved_date = Column(DateTime(timezone=True))
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    location = relationship("Location", back_populates="reorder_requests")
    items = relationship("ReorderRequestItem", back_populates="reorder_request")