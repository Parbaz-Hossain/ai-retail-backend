from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, validator
from datetime import datetime, date
from app.models.shared.enums import PurchaseOrderStatus

class PurchaseOrderItemBase(BaseModel):
    item_id: int
    quantity: Decimal
    unit_cost: Decimal

    @validator('quantity', 'unit_cost')
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('Quantity and unit cost must be positive')
        return v

class PurchaseOrderItemCreate(PurchaseOrderItemBase):
    pass

class PurchaseOrderItemResponse(PurchaseOrderItemBase):
    id: int
    purchase_order_id: int
    total_cost: Decimal
    received_quantity: Decimal
    item_name: Optional[str] = None
    item_code: Optional[str] = None

    class Config:
        from_attributes = True

class PurchaseOrderBase(BaseModel):
    supplier_id: int
    order_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    tax_amount: Optional[Decimal] = Decimal('0')
    discount_amount: Optional[Decimal] = Decimal('0')

class PurchaseOrderCreate(PurchaseOrderBase):
    items: List[PurchaseOrderItemCreate]

    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError('Purchase order must have at least one item')
        return v

class PurchaseOrderUpdate(BaseModel):
    supplier_id: Optional[int] = None
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    tax_amount: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    items: Optional[List[PurchaseOrderItemCreate]] = None

class PurchaseOrderResponse(PurchaseOrderBase):
    id: int
    po_number: str
    status: PurchaseOrderStatus
    subtotal: Decimal
    total_amount: Decimal
    requested_by: Optional[int]
    approved_by: Optional[int]
    approved_date: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    items: List[PurchaseOrderItemResponse] = []
    supplier_name: Optional[str] = None

    class Config:
        from_attributes = True