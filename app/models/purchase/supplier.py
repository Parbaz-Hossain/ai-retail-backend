from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class Supplier(BaseModel):
    __tablename__ = 'suppliers'
    
    supplier_code = Column(String(20), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    contact_person = Column(String(100))
    email = Column(String(100))
    phone = Column(String(20))
    mobile = Column(String(20))
    address = Column(Text)
    city = Column(String(50))
    state = Column(String(50))
    postal_code = Column(String(20))
    country = Column(String(50), default="Bangladesh")
    tax_number = Column(String(50))
    payment_terms = Column(String(100))
    credit_limit = Column(Numeric(12, 2))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    item_suppliers = relationship("ItemSupplier", back_populates="supplier")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")