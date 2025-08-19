from pydantic import BaseModel
from typing import Dict, List

class StockSummaryResponse(BaseModel):
    location_id: int
    total_items: int
    total_stock: float
    total_reserved: float
    total_available: float
    low_stock_items: int

class MovementSummaryResponse(BaseModel):
    summary_by_type: Dict[str, Dict[str, float]]
    total_movements: int
    total_value: float

# Bulk operation schemas
class BulkStockAdjustment(BaseModel):
    adjustments: List[Dict[str, any]]  # [{item_id, location_id, quantity_change, reason}]

class BulkTransferRequest(BaseModel):
    from_location_id: int
    to_location_id: int
    items: List[Dict[str, any]]  # [{item_id, quantity}]