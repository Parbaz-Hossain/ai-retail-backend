from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import TransferStatus

class Transfer(BaseModel):
    __tablename__ = 'transfers'
    
    transfer_number = Column(String(50), unique=True, nullable=False)
    from_location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    to_location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    transfer_date = Column(Date, nullable=False)
    expected_date = Column(Date)
    status = Column(SQLEnum(TransferStatus), default=TransferStatus.PENDING)
    requested_by = Column(Integer)  # User ID
    approved_by = Column(Integer)  # User ID
    sent_by = Column(Integer)  # User ID
    received_by = Column(Integer)  # User ID
    approved_date = Column(DateTime(timezone=True))
    sent_date = Column(DateTime(timezone=True))
    received_date = Column(DateTime(timezone=True))
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    from_location = relationship("Location", foreign_keys=[from_location_id], back_populates="transfers_from")
    to_location = relationship("Location", foreign_keys=[to_location_id], back_populates="transfers_to")
    items = relationship("TransferItem", back_populates="transfer")