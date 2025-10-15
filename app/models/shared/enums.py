from sqlalchemy.ext.declarative import declarative_base
from enum import Enum

Base = declarative_base()

# Enums
class UnitType(str, Enum):
    PCS = "PCS"        # Piece
    KG = "KG"          # Kilogram
    G = "G"            # Gram
    MG = "MG"          # Milligram
    L = "L"            # Liter
    ML = "ML"          # Milliliter
    M2 = "M2"          # Square Meter
    M3 = "M3"          # Cubic Meter
    LM = "LM"          # Linear Meter
    CM = "CM"          # Centimeter
    MM = "MM"          # Millimeter
    IN = "IN"          # Inch
    BAG = "BAG"
    BOX = "BOX"
    CARTON = "CARTON"
    BTL = "BTL"        # Bottle
    DOZEN = "DOZEN"

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
    WEEKEND = "WEEKEND"  
    HOLIDAY = "HOLIDAY"

class SalaryPaymentStatus(str, Enum):
    PAID = "PAID"
    UNPAID = "UNPAID"

class SalaryPaymentStatus(str, Enum):
    PENDING = "Pending"
    PAID = "Paid"
    UNPAID = "UNPAID"
    FAILED = "Failed"

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

class HistoryActionType(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    VIEW = "VIEW"
    SEARCH = "SEARCH"
    EXPORT = "EXPORT"
    CHAT_MESSAGE = "CHAT_MESSAGE"
    TASK_COMPLETE = "TASK_COMPLETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"


# Task related enums
class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    OVERDUE = "OVERDUE"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class TaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"

class TaskCategory(str, Enum):
    INVENTORY = "INVENTORY"
    HR = "HR"
    PURCHASE = "PURCHASE"
    LOGISTICS = "LOGISTICS"
    MAINTENANCE = "MAINTENANCE"
    FINANCE = "FINANCE"
    CUSTOMER_SERVICE = "CUSTOMER_SERVICE"
    OPERATIONS = "OPERATIONS"
    QUALITY_CONTROL = "QUALITY_CONTROL"

class ReferenceType(str, Enum):
    # Inventory related
    LOW_STOCK_ALERT = "LOW_STOCK_ALERT"
    REORDER_REQUEST = "REORDER_REQUEST"
    STOCK_COUNT = "STOCK_COUNT"
    TRANSFER_REQUEST = "TRANSFER_REQUEST"
    EXPIRED_ITEMS = "EXPIRED_ITEMS"
    
    # HR related
    SALARY_GENERATION = "SALARY_GENERATION"
    ATTENDANCE_REVIEW = "ATTENDANCE_REVIEW"
    EMPLOYEE_ONBOARDING = "EMPLOYEE_ONBOARDING"
    SCHEDULE_REVIEW = "SCHEDULE_REVIEW"
    
    # Purchase related
    PURCHASE_ORDER = "PURCHASE_ORDER"
    SUPPLIER_EVALUATION = "SUPPLIER_EVALUATION"
    GOODS_RECEIPT = "GOODS_RECEIPT"
    
    # Logistics related
    SHIPMENT_DELIVERY = "SHIPMENT_DELIVERY"
    VEHICLE_MAINTENANCE = "VEHICLE_MAINTENANCE"
    DRIVER_ASSIGNMENT = "DRIVER_ASSIGNMENT"
    
    # General
    EQUIPMENT_MAINTENANCE = "EQUIPMENT_MAINTENANCE"
    MONTHLY_REPORT = "MONTHLY_REPORT"
    CUSTOMER_COMPLAINT = "CUSTOMER_COMPLAINT"

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class OffdayType(str, Enum):
    WEEKEND = "WEEKEND"
    PERSONAL_OFFDAY = "PERSONAL_OFFDAY"
    COMPENSATORY_OFF = "COMPENSATORY_OFF"

class DeductionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"

class PaymentStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class PaymentType(Enum):
    REGULAR = "REGULAR"
    CLOSE = "CLOSE"

# region Approval System Enums

class ApprovalRequestType(str, Enum):
    SHIFT = "SHIFT"
    SALARY = "SALARY"
    OFFDAY = "OFFDAY"

class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class ApprovalResponseStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

# endregion