from sqlalchemy import Column, Integer, String, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from uuid import uuid4
from sqlalchemy.types import Uuid
from app.db.base import BaseModel
from app.models.shared.enums import UnitType

class Product(BaseModel):
    __tablename__ = 'products'
    
    product_guid = Column(Uuid(as_uuid=True), unique=True, default=uuid4)
    product_code = Column(String(50), unique=True, index=True, nullable=True)
    name = Column(String(1000), nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey('categories.id'))
    selling_price = Column(Numeric(10, 2))
    cost_price = Column(Numeric(10, 2))  # Calculated from ingredients
    preparation_time = Column(Integer)  # In minutes
    barcode = Column(String(100))
    qr_code = Column(String(255))
    image_url = Column(String(255))
    is_available = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    category = relationship("Category", back_populates="products")
    product_items = relationship("ProductItem", back_populates="product", cascade="all, delete-orphan")
    