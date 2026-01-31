from sqlalchemy import Column, Integer, Numeric, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.base import BaseModel
from app.models.shared.enums import UnitType

class ProductItem(BaseModel):
    __tablename__ = 'product_items'
    
    product_id = Column(Integer, ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    unit_type = Column(SQLEnum(UnitType), nullable=False)
    quantity = Column(Numeric(10, 4), nullable=False)  # Quantity of item needed for one product unit
    unit_cost = Column(Numeric(10, 2))  # Cost at the time of recipe creation
    notes = Column(Text)  # Special preparation notes for this ingredient
    
    # Relationships
    product = relationship("Product", back_populates="product_items")
    item = relationship("Item", back_populates="product_items")
    