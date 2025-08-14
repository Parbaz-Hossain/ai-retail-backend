from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import UnitType

class Item(BaseModel):
    __tablename__ = 'items'
    
    item_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey('categories.id'))
    stock_type_id = Column(Integer, ForeignKey('stock_types.id'))
    unit_type = Column(SQLEnum(UnitType), nullable=False)
    unit_cost = Column(Numeric(10, 2))
    selling_price = Column(Numeric(10, 2))
    barcode = Column(String(100))
    qr_code = Column(String(255))
    image_url = Column(String(255))
    is_perishable = Column(Boolean, default=False)
    shelf_life_days = Column(Integer)
    minimum_stock_level = Column(Numeric(10, 2), default=0)
    maximum_stock_level = Column(Numeric(10, 2), default=0)
    reorder_point = Column(Numeric(10, 2), default=0)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    category = relationship("Category", back_populates="items")
    stock_type = relationship("StockType", back_populates="items")
    stock_levels = relationship("StockLevel", back_populates="item")
    stock_movements = relationship("StockMovement", back_populates="item")
    item_suppliers = relationship("ItemSupplier", back_populates="item")
    purchase_order_items = relationship("PurchaseOrderItem", back_populates="item")
    reorder_request_items = relationship("ReorderRequestItem", back_populates="item")
    transfer_items = relationship("TransferItem", back_populates="item")
    inventory_count_items = relationship("InventoryCountItem", back_populates="item")