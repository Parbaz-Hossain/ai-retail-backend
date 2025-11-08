from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid
from uuid import uuid4
from app.db.base import BaseModel

class Order(BaseModel):
    __tablename__ = 'orders'
    
    # Foodics fields
    foodics_guid = Column(Uuid(as_uuid=True), unique=True, nullable=False)
    app_id = Column(Uuid(as_uuid=True))
    promotion_id = Column(Uuid(as_uuid=True), nullable=True)
    
    # Order identification
    order_number = Column(String(50), unique=True, nullable=False)
    reference = Column(Integer, nullable=False, index=True)
    reference_x = Column(String(50))
    check_number = Column(Integer)
    
    # Order details
    order_type = Column(Integer, default=0)  # Dine-in, Takeaway, Delivery, etc.
    source = Column(Integer, default=0)  # POS, Mobile App, Web, etc.
    status = Column(Integer, default=0)  # 0=Open, 1=Closed, 7=Cancelled, 5=Returned etc.
    delivery_status = Column(Integer, nullable=True)
    guests = Column(Integer, default=0)
    
    # Pricing
    discount_type = Column(Integer, nullable=True)
    subtotal_price = Column(Numeric(12, 2), default=0)
    discount_amount = Column(Numeric(12, 2), default=0)
    rounding_amount = Column(Numeric(12, 2), default=0)
    total_price = Column(Numeric(12, 2), default=0)
    tax_exclusive_discount_amount = Column(Numeric(12, 2), default=0)
    
    # Notes
    kitchen_notes = Column(Text)
    customer_notes = Column(Text)
    
    # Dates
    business_date = Column(Date, nullable=False)
    opened_at = Column(DateTime(timezone=True))
    accepted_at = Column(DateTime(timezone=True))
    due_at = Column(DateTime(timezone=True))
    driver_assigned_at = Column(DateTime(timezone=True))
    dispatched_at = Column(DateTime(timezone=True))
    driver_collected_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    
    # Location reference
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False)
    
    # Additional tracking
    is_synced = Column(Boolean, default=True)
    sync_error = Column(Text)
    
    # Relationships
    location = relationship("Location", back_populates="orders")
    order_products = relationship("OrderProduct", back_populates="order", cascade="all, delete-orphan")