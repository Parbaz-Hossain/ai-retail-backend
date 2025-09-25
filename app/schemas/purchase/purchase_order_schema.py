from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, validator
from datetime import datetime, date
from app.models.shared.enums import PurchaseOrderStatus

class ItemInfo(BaseModel):
    item_code: str
    name: str

    class Config:
        from_attributes = True

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
    item : Optional[ItemInfo] = None
    total_cost: Decimal
    received_quantity: Decimal

    class Config:
        from_attributes = True

class PurchaseOrderBase(BaseModel):
    supplier_id: int
    order_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    payment_conditions: Optional[str] = None
    tax_amount: Optional[Decimal] = Decimal('0')
    discount_amount: Optional[Decimal] = Decimal('0')

class PurchaseOrderCreate(PurchaseOrderBase):
    pass

class PurchaseOrderUpdate(BaseModel):
    supplier_id: Optional[int] = None
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    payment_conditions: Optional[str] = None
    tax_amount: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None

class SupplierInfo(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class PurchaseOrderResponse(PurchaseOrderBase):
    id: int
    po_number: str
    status: PurchaseOrderStatus
    subtotal: Decimal
    total_amount: Decimal
    file_paths: Optional[List[str]] = None
    requested_by: Optional[int]
    approved_by: Optional[int]
    approved_date: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    items: List[PurchaseOrderItemResponse] = []
    supplier: Optional[SupplierInfo] = None

    # NEW PAYMENT FIELDS
    paid_amount: Optional[Decimal]= None
    paid_percentage: Optional[Decimal] = None
    remaining_amount: Optional[Decimal] = None
    is_closed: Optional[bool] = None

    class Config:
        from_attributes = True