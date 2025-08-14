from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class TransferItem(BaseModel):
    __tablename__ = 'transfer_items'
    
    transfer_id = Column(Integer, ForeignKey('transfers.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    requested_quantity = Column(Numeric(10, 2), nullable=False)
    sent_quantity = Column(Numeric(10, 2))
    received_quantity = Column(Numeric(10, 2))
    unit_cost = Column(Numeric(10, 2))
    batch_number = Column(String(50))
    expiry_date = Column(Date)
    
    # Relationships
    transfer = relationship("Transfer", back_populates="items")
    item = relationship("Item", back_populates="transfer_items")