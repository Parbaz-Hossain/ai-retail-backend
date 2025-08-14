from sqlalchemy.ext.declarative import declarative_base
from enum import Enum

Base = declarative_base()

# Enums
class UnitType(str, Enum):
    PCS = "PCS"
    KG = "KG"
    M2 = "M2"
    M3 = "M3"
    L = "L"
    LM = "LM"

class StockMovementType(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    TRANSFER = "TRANSFER"
    WASTE = "WASTE"
    DAMAGE = "DAMAGE"
    EXPIRED = "EXPIRED"
    ADJUSTMENT = "ADJUSTMENT"

class PurchaseOrderStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"

class ShipmentStatus(str, Enum):
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    PICKED_UP = "PICKED_UP"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

class AttendanceStatus(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    LEFT_EARLY = "LEFT_EARLY"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"

class SalaryPaymentStatus(str, Enum):
    PAID = "PAID"
    UNPAID = "UNPAID"

class ReorderRequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"

class TransferStatus(str, Enum):
    PENDING = "PENDING"
    IN_TRANSIT = "IN_TRANSIT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"