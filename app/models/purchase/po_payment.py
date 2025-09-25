from app.models.shared.enums import PaymentStatus, PaymentType
from sqlalchemy import Column, Integer, DateTime, Text, Numeric, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from app.db.base import BaseModel


class POPayment(BaseModel):
    __tablename__ = 'po_payments'
    
    purchase_order_id = Column(Integer, ForeignKey('purchase_orders.id'), nullable=False)
    payment_amount = Column(Numeric(12, 2), nullable=False)
    payment_type = Column(SQLEnum(PaymentType), default=PaymentType.REGULAR)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    notes = Column(Text)
    file_paths = Column(JSON)  # For multiple file uploads
    requested_by = Column(Integer, nullable=False)  # User ID
    approved_by = Column(Integer)  # Manager User ID
    approved_date = Column(DateTime(timezone=True))
    
    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="payments")