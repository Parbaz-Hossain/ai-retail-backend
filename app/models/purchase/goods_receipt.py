from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class GoodsReceipt(BaseModel):
    __tablename__ = 'goods_receipts'
    
    receipt_number = Column(String(50), unique=True, nullable=False)
    purchase_order_id = Column(Integer, ForeignKey('purchase_orders.id'), nullable=False)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
    receipt_date = Column(Date, nullable=False)
    # delivered_by = Column(String(100))
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    received_by = Column(Integer)  # Employee ID
    notes = Column(Text)
    
    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="goods_receipts")
    supplier = relationship("Supplier")
    items = relationship("GoodsReceiptItem", back_populates="goods_receipt")
    location = relationship("Location")