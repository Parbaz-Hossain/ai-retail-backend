from sqlalchemy import Column, Integer, ForeignKey, Numeric, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SQLEnum
from app.db.base import BaseModel
from app.models.shared.enums import UnitType

class ItemIngredient(BaseModel):
    __tablename__ = 'item_ingredients'
    
    item_id = Column(Integer, ForeignKey('items.id'), nullable=False, index=True)
    ingredient_item_id = Column(Integer, ForeignKey('items.id'), nullable=False, index=True)
    quantity = Column(Numeric(10, 3), nullable=False)
    unit_type = Column(SQLEnum(UnitType), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    # Parent item (the item that contains this ingredient)
    item = relationship("Item", foreign_keys=[item_id], back_populates="ingredients")    
    # The ingredient item (the item being used as ingredient)
    ingredient_item = relationship("Item", foreign_keys=[ingredient_item_id], back_populates="used_as_ingredient_in")