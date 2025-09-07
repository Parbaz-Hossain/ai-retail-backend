from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class PurchaseMetrics(BaseModel):
    today_purchase: float
    total_purchase_orders: int
    pending_approvals: int

class PurchaseReport(BaseModel):
    total_purchase: float
    monthly_purchase_data: List[Dict[str, Any]]

class EmployeeMetrics(BaseModel):
    active_employees: int
    total_employees: int

class EmployeeReport(BaseModel):
    on_duty_today: int
    staff_status: List[Dict[str, Any]]

class StockMetrics(BaseModel):
    low_stock_items: int
    total_items: int

class ItemAvailabilityReport(BaseModel):
    item_availability: List[Dict[str, Any]]

class SalaryMetrics(BaseModel):
    individual_salaries: List[Dict[str, Any]]

class SalaryReport(BaseModel):
    total_salary_paid: float
    monthly_salaries: List[Dict[str, Any]]

class YearlySalaryReport(BaseModel):
    year: int
    total_paid_salary: float
    monthly_breakdown: List[Dict[str, Any]]

class VehicleMetrics(BaseModel):
    available_vehicles: int
    engaged_vehicles: int
    not_available_vehicles: int
    vehicle_status: List[Dict[str, Any]]

class DriverMetrics(BaseModel):
    available_drivers: int
    engaged_drivers: int
    not_available_drivers: int
    driver_status: List[Dict[str, Any]]

class ShiftInfo(BaseModel):
    current_shift: Optional[Dict[str, Any]]
    next_shift: Optional[Dict[str, Any]]

class AttendanceMetrics(BaseModel):
    monthly_attendance: List[Dict[str, Any]]
    today_present: int
    today_absent: int

class ShipmentMetrics(BaseModel):
    total_shipments: int
    status_breakdown: List[Dict[str, Any]]
    shipment_products: List[Dict[str, Any]]

class ReorderMetrics(BaseModel):
    pending_requests: int
    approved_requests: int
    rejected_requests: int
    recent_requests: List[Dict[str, Any]]

class HolidayInfo(BaseModel):
    upcoming_holidays: List[Dict[str, Any]]
    today_holiday: Optional[Dict[str, Any]]

class DashboardResponse(BaseModel):
    purchase_metrics: PurchaseMetrics
    employee_metrics: EmployeeMetrics
    stock_metrics: StockMetrics
    salary_metrics: SalaryMetrics
    po_approvals: List[Dict[str, Any]]
    shift_info: ShiftInfo
    reorder_metrics: ReorderMetrics
    holiday_info: HolidayInfo