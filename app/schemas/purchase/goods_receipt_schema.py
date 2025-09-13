from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, validator
from datetime import datetime, date


class ItemInfo(BaseModel):
    item_code: str
    name: str

    class Config:
        from_attributes = True

class LocationInfo(BaseModel):
    name: str

    class Config:
        from_attributes = True

class GoodsReceiptItemBase(BaseModel):
    purchase_order_item_id: int
    received_quantity: Decimal
    batch_number: Optional[str] = None
    expiry_date: Optional[date] = None
    location_id: int

    @validator('received_quantity')
    def validate_positive_quantity(cls, v):
        if v <= 0:
            raise ValueError('Received quantity must be positive')
        return v

class GoodsReceiptItemCreate(GoodsReceiptItemBase):
    pass

class GoodsReceiptItemResponse(GoodsReceiptItemBase):
    id: int
    goods_receipt_id: int
    item_id: int    
    item : Optional[ItemInfo] = None
    ordered_quantity: Decimal
    unit_cost: Decimal    
    location : Optional[LocationInfo] = None

    class Config:
        from_attributes = True

class GoodsReceiptBase(BaseModel):
    purchase_order_id: int
    receipt_date: Optional[date] = None
    delivered_by: Optional[str] = None
    notes: Optional[str] = None

class GoodsReceiptCreate(GoodsReceiptBase):
    items: List[GoodsReceiptItemCreate]

    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError('Goods receipt must have at least one item')
        return v

class GoodsReceiptUpdate(BaseModel):
    delivered_by: Optional[str] = None
    notes: Optional[str] = None
    updated_by: Optional[int] = None

class SupplierInfo(BaseModel):
    name: str

    class Config:
        from_attributes = True

class PurchaseOrderInfo(BaseModel):
    po_number: str
    order_date: date
    total_amount: Decimal

    class Config:
        from_attributes = True

class GoodsReceiptResponse(GoodsReceiptBase):
    id: int
    receipt_number: str
    supplier_id: int
    supplier: Optional[SupplierInfo] = None
    received_by: int
    created_at: datetime
    updated_at: Optional[datetime]
    items: List[GoodsReceiptItemResponse] = []
    purchase_order: Optional[PurchaseOrderInfo] = None
    received_by_name: Optional[str] = None

    class Config:
        from_attributes = True