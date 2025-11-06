from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid
from app.db.base import BaseModel

class OrderProduct(BaseModel):
    __tablename__ = 'order_products'
    
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)  # Nullable if product not found
    
    # Foodics product reference
    foodics_product_guid = Column(Uuid(as_uuid=True))
    product_name = Column(String(500), nullable=False)
    
    # Quantities and pricing
    quantity = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(10, 2), default=0)
    total_price = Column(Numeric(12, 2), default=0)
    discount_amount = Column(Numeric(12, 2), default=0)
    
    # Additional info
    notes = Column(Text)
    
    # Relationships
    order = relationship("Order", back_populates="order_products")
    product = relationship("Product")