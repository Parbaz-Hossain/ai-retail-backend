from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class StockSummaryResponse(BaseModel):
    location_id: int
    total_items: int
    total_stock: float
    total_reserved: float
    total_available: float
    low_stock_items: int

class MovementSummaryResponse(BaseModel):
    summary_by_type: Dict[str, Dict[str, float]]
    total_movements: Optional[int] = None
    total_value: Optional[float] = None

# Bulk operation schemas
class BulkStockAdjustment(BaseModel):
    adjustments: List[Dict[str, Any]]  # [{item_id, location_id, quantity_change, reason}]

class BulkTransferRequest(BaseModel):
    from_location_id: int
    to_location_id: int
    items: List[Dict[str, Any]]  # [{item_id, quantity}]