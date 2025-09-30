from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, validator
from datetime import datetime
from app.models.purchase.po_payment import PaymentStatus, PaymentType

class POPaymentBase(BaseModel):
    purchase_order_id: int
    payment_amount: Decimal
    payment_type: PaymentType = PaymentType.REGULAR
    notes: Optional[str] = None

    @validator('payment_amount')
    def validate_positive_amount(cls, v):
        if v <= 0:
            raise ValueError('Payment amount must be positive')
        return v

class POPaymentCreate(POPaymentBase):
    pass

class POPaymentUpdate(BaseModel):
    payment_amount: Optional[Decimal] = None
    notes: Optional[str] = None

    @validator('payment_amount')
    def validate_positive_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Payment amount must be positive')
        return v

class PurchaseOrder(BaseModel):
    po_number: str
    total_amount: Decimal

    class Config:
        from_attributes = True

class POPaymentResponse(POPaymentBase):
    id: int
    status: PaymentStatus
    file_paths: Optional[List[str]] = None
    purchase_order: Optional[PurchaseOrder] = None
    requested_by: int
    approved_by: Optional[int] = None
    approved_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True