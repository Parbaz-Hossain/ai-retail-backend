from pydantic import BaseModel, field_serializer
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

# Lightweight references
class LocationRef(BaseModel):
    id: int
    name: str
    location_type: str
    
    class Config:
        from_attributes = True

class ProductRef(BaseModel):
    id: int
    name: str
    product_code: Optional[str] = None
    
    class Config:
        from_attributes = True

# OrderProduct schemas
class OrderProductBase(BaseModel):
    product_id: Optional[int] = None
    foodics_product_guid: Optional[UUID] = None
    product_name: str
    quantity: Decimal
    unit_price: Decimal = 0
    total_price: Decimal = 0
    discount_amount: Decimal = 0
    notes: Optional[str] = None

class OrderProductCreate(OrderProductBase):
    pass

class OrderProductInDB(OrderProductBase):
    id: int
    order_id: int
    created_at: Optional[datetime] = None
    
    @field_serializer('foodics_product_guid')
    def serialize_uuid(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value else None
    
    class Config:
        from_attributes = True

class OrderProduct(OrderProductInDB):
    product: Optional[ProductRef] = None

# Order schemas
class OrderBase(BaseModel):
    order_number: str
    reference: int
    location_id: int
    status: int = 0
    order_type: int = 0
    source: int = 0
    business_date: date
    subtotal_price: Decimal = 0
    discount_amount: Decimal = 0
    total_price: Decimal = 0
    kitchen_notes: Optional[str] = None
    customer_notes: Optional[str] = None

class OrderCreate(OrderBase):
    foodics_guid: UUID
    app_id: Optional[UUID] = None
    promotion_id: Optional[UUID] = None
    reference_x: Optional[str] = None
    check_number: Optional[int] = None
    delivery_status: Optional[int] = None
    guests: int = 0
    discount_type: Optional[int] = None
    rounding_amount: Decimal = 0
    tax_exclusive_discount_amount: Decimal = 0
    opened_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    driver_assigned_at: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    driver_collected_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

class OrderInDB(OrderCreate):
    id: int
    is_synced: bool = True
    sync_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_serializer('foodics_guid', 'app_id', 'promotion_id')
    def serialize_uuid(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value else None
    
    class Config:
        from_attributes = True

class Order(OrderInDB):
    location: Optional[LocationRef] = None
    order_products: List[OrderProduct] = []

# Foodics sync request/response
class FoodicsSyncRequest(BaseModel):
    location_id: Optional[int] = None  # Sync specific location or all

class FoodicsSyncResponse(BaseModel):
    success: bool
    message: str
    orders_synced: int
    errors: List[str] = []