from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class GoodsReceiptItem(BaseModel):
    __tablename__ = 'goods_receipt_items'
    
    goods_receipt_id = Column(Integer, ForeignKey('goods_receipts.id'), nullable=False)
    purchase_order_item_id = Column(Integer, ForeignKey('purchase_order_items.id'), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False)
    ordered_quantity = Column(Numeric(10, 2), nullable=False)
    received_quantity = Column(Numeric(10, 2), nullable=False)
    unit_cost = Column(Numeric(10, 2), nullable=False)
    batch_number = Column(String(50))
    expiry_date = Column(Date)    
    
    # Relationships
    goods_receipt = relationship("GoodsReceipt", back_populates="items")
    purchase_order_item = relationship("PurchaseOrderItem")
    item = relationship("Item")
    