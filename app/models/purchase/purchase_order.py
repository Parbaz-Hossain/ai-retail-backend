from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import PurchaseOrderStatus

class PurchaseOrder(BaseModel):
    __tablename__ = 'purchase_orders'
    
    po_number = Column(String(50), unique=True, nullable=False)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    order_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date)
    status = Column(SQLEnum(PurchaseOrderStatus), default=PurchaseOrderStatus.DRAFT)
    subtotal = Column(Numeric(12, 2), default=0)
    tax_amount = Column(Numeric(12, 2), default=0)
    discount_amount = Column(Numeric(12, 2), default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    notes = Column(Text)
    payment_conditions = Column(String(500))  
    file_paths = Column(JSON)  
    requested_by = Column(Integer)  # User ID
    approved_by = Column(Integer)  # User ID
    approved_date = Column(DateTime(timezone=True))
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)

    # NEW PAYMENT FIELDS
    paid_amount = Column(Numeric(12, 2), default=0)
    paid_percentage = Column(Numeric(5, 2), default=0)  # 0.00 to 100.00
    is_closed = Column(Boolean, default=False)
    
    # Relationships
    supplier = relationship("Supplier", back_populates="purchase_orders")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order")
    goods_receipts = relationship("GoodsReceipt", back_populates="purchase_order")
    payments = relationship("POPayment", back_populates="purchase_order")
    location = relationship("Location", back_populates="purchase_orders")