from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class Category(BaseModel):
    __tablename__ = 'categories'
    
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey('categories.id'))
    is_active = Column(Boolean, default=True)
    
    # Self-referential relationship for parent/child categories
    parent = relationship("Category", remote_side=[id], backref="subcategories")
    items = relationship("Item", back_populates="category")