# app/schemas/reports/report_schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import date, datetime
from decimal import Decimal

# =================== COMMON SCHEMAS ===================

class ReportFilterBase(BaseModel):
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    location_id: Optional[int] = None
    search: Optional[str] = None

class PaginationParams(BaseModel):
    page_index: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)

# =================== INVENTORY REPORT SCHEMAS ===================

class StockLevelReportItem(BaseModel):
    sl: int
    sku: str
    item_name: str
    category: str
    location: str
    current_stock: float
    available_stock: float
    reserved_stock: float
    minimum_stock: float
    maximum_stock: float
    reorder_point: float
    unit_cost: float
    stock_value: float
    stock_status: str  # OUT_OF_STOCK, LOW, NORMAL, HIGH
    priority: str      # CRITICAL, HIGH, MEDIUM, LOW
    unit: str

class StockMovementReportItem(BaseModel):
    sl: int
    sku: str
    item_name: str
    location: str
    movement_type: str
    quantity: float
    unit_cost: float
    total_value: float
    reference_type: Optional[str]
    reference_id: Optional[int]
    batch_number: Optional[str]
    expiry_date: Optional[str]
    remarks: Optional[str]
    movement_date: Optional[str]
    transaction_direction: str  # IN, OUT

class LowStockAlertItem(BaseModel):
    sl: int
    sku: str
    item_name: str
    category: str
    location: str
    current_stock: float
    reorder_point: float
    minimum_stock: float
    shortage_quantity: float
    priority: str
    unit: str
    unit_cost: float
    estimated_reorder_cost: float
    days_out_of_stock: int

class ItemPerformanceItem(BaseModel):
    sl: int
    sku: str
    item_name: str
    category: str
    total_movements: int
    inbound_quantity: float
    outbound_quantity: float
    turnover_rate: float
    average_stock_level: float
    stock_velocity: float
    performance_score: float

# =================== PURCHASE REPORT SCHEMAS ===================

class PurchaseOrderSummaryItem(BaseModel):
    sl: int
    po_number: str
    supplier_name: str
    order_date: str
    expected_delivery_date: Optional[str]
    status: str
    total_amount: float
    total_items: int
    total_quantity: float
    total_received: float
    receipt_status: str  # COMPLETED, PARTIAL, PENDING
    completion_percentage: float
    approved_date: Optional[str]
    days_pending: Optional[int]

class SupplierPerformanceItem(BaseModel):
    sl: int
    supplier_name: str
    total_orders: int
    total_value: float
    on_time_deliveries: int
    late_deliveries: int
    delivery_performance: float  # percentage
    average_lead_time: float     # days
    quality_score: float
    cost_competitiveness: float
    overall_rating: str          # EXCELLENT, GOOD, AVERAGE, POOR

class PurchaseSpendingItem(BaseModel):
    sl: int
    category: str
    supplier_name: Optional[str]
    period: str
    total_spent: float
    total_orders: int
    average_order_value: float
    percentage_of_total: float
    year_over_year_change: float

# =================== HR REPORT SCHEMAS ===================

class AttendanceSummaryItem(BaseModel):
    sl: int
    employee_name: str
    employee_id: str
    department: str
    total_days: int
    present_days: int
    absent_days: int
    late_days: int
    attendance_percentage: float
    total_hours: float
    overtime_hours: float
    status: str  # EXCELLENT, GOOD, NEEDS_IMPROVEMENT

class SalarySummaryItem(BaseModel):
    sl: int
    employee_name: str
    employee_id: str
    department: str
    salary_month: str
    basic_salary: float
    gross_salary: float
    total_deductions: float
    net_salary: float
    payment_status: str  # PAID, UNPAID
    payment_date: Optional[str]

# =================== LOGISTICS REPORT SCHEMAS ===================

class ShipmentTrackingItem(BaseModel):
    sl: int
    shipment_number: str
    from_location: str
    to_location: str
    driver_name: Optional[str]
    vehicle_number: Optional[str]
    shipment_date: str
    expected_delivery: Optional[str]
    actual_delivery: Optional[str]
    status: str
    total_items: int
    delay_days: Optional[int]
    delivery_performance: str  # ON_TIME, DELAYED, EARLY

# =================== TASK MANAGEMENT SCHEMAS ===================

class TaskPerformanceItem(BaseModel):
    sl: int
    task_number: str
    title: str
    assigned_to: str
    department: str
    priority: str
    status: str
    created_date: str
    due_date: Optional[str]
    completed_date: Optional[str]
    estimated_hours: Optional[float]
    actual_hours: Optional[float]
    efficiency_ratio: Optional[float]
    overdue_days: Optional[int]

# =================== FINANCIAL SCHEMAS ===================

class CostAnalysisItem(BaseModel):
    sl: int
    cost_category: str
    period: str
    department: Optional[str]
    location: Optional[str]
    budgeted_amount: float
    actual_amount: float
    variance: float
    variance_percentage: float
    trend: str  # INCREASING, DECREASING, STABLE

# =================== ANALYTICS SCHEMAS ===================

class DemandForecastItem(BaseModel):
    sl: int
    sku: str
    productName: str
    category: str
    location: str
    forecastPeriod: str  # weekly, monthly, quarterly
    currentSalesData: int
    plannedSalesTarget: int
    demandVariationPercentage: float
    averageDailyDemand: float
    transactionCount: int
    forecastAccuracy: float

class PerformanceInsight(BaseModel):
    category: str  # inventory, purchase, hr, logistics
    insight_type: str  # opportunity, risk, trend, recommendation
    title: str
    description: str
    impact_level: str  # HIGH, MEDIUM, LOW
    recommended_action: str
    potential_savings: Optional[float]
    implementation_effort: str  # LOW, MEDIUM, HIGH
    priority_score: float

# =================== DASHBOARD SCHEMAS ===================

class InventoryOverview(BaseModel):
    total_items: int
    total_locations: int
    total_inventory_value: float
    low_stock_items: int
    out_of_stock_items: int
    high_stock_items: int
    inventory_turnover: float

class PurchaseOverview(BaseModel):
    total_purchase_orders: int
    total_purchase_value: float
    pending_orders: int
    completed_orders: int
    average_lead_time: float
    on_time_delivery_rate: float

class TaskOverview(BaseModel):
    total_tasks: int
    pending_tasks: int
    completed_tasks: int
    overdue_tasks: int
    completion_rate: float
    average_completion_time: float

class HROverview(BaseModel):
    total_employees: int
    present_today: int
    absent_today: int
    attendance_rate: float
    pending_salaries: int
    total_payroll: float

class LogisticsOverview(BaseModel):
    active_shipments: int
    completed_deliveries: int
    delayed_shipments: int
    on_time_delivery_rate: float
    total_vehicles: int
    available_drivers: int

class ExecutiveDashboard(BaseModel):
    reporting_period: str
    last_updated: datetime
    inventory_overview: InventoryOverview
    purchase_overview: PurchaseOverview
    task_overview: TaskOverview
    hr_overview: Optional[HROverview]
    logistics_overview: Optional[LogisticsOverview]
    key_metrics: Dict[str, Any]
    alerts: List[Dict[str, Any]]
    trends: List[Dict[str, Any]]

# =================== ADVANCED ANALYTICS SCHEMAS ===================

class PredictiveAnalytics(BaseModel):
    forecast_type: str  # demand, stock, cost
    prediction_period: str
    accuracy_score: float
    confidence_interval: Dict[str, float]
    key_drivers: List[str]
    recommendations: List[str]

class BusinessIntelligence(BaseModel):
    kpi_name: str
    current_value: float
    target_value: float
    previous_period_value: float
    trend: str  # UP, DOWN, STABLE
    performance_status: str  # ABOVE_TARGET, ON_TARGET, BELOW_TARGET
    insights: List[str]

# =================== EXPORT SCHEMAS ===================

class ReportExportRequest(BaseModel):
    report_type: str
    format: str = "excel"  # excel, csv, pdf
    filters: Dict[str, Any] = {}
    include_charts: bool = True
    email_recipients: Optional[List[str]] = None

class ReportExportResponse(BaseModel):
    export_id: str
    status: str  # PROCESSING, COMPLETED, FAILED
    download_url: Optional[str]
    file_size: Optional[int]
    created_at: datetime
    expires_at: datetime

# =================== ALERT SCHEMAS ===================

class SystemAlert(BaseModel):
    alert_id: str
    alert_type: str  # STOCK_LOW, OVERDUE_TASK, DELAYED_SHIPMENT
    severity: str    # CRITICAL, HIGH, MEDIUM, LOW
    title: str
    message: str
    entity_type: str
    entity_id: int
    created_at: datetime
    acknowledged: bool
    action_required: str

# =================== COMPARISON REPORTS ===================

class PeriodComparisonItem(BaseModel):
    metric_name: str
    current_period: float
    previous_period: float
    change_amount: float
    change_percentage: float
    trend: str
    performance: str

class LocationComparisonItem(BaseModel):
    location_name: str
    metric_value: float
    rank: int
    percentage_of_total: float
    performance_vs_average: float

# =================== AUDIT TRAIL SCHEMAS ===================

class AuditTrailItem(BaseModel):
    sl: int
    timestamp: datetime
    user_name: str
    action: str
    resource: str
    resource_id: Optional[int]
    old_value: Optional[str]
    new_value: Optional[str]
    ip_address: Optional[str]
    success: bool

# =================== RESPONSE WRAPPERS ===================

class ReportMetadata(BaseModel):
    report_name: str
    generated_at: datetime
    generated_by: str
    total_records: int
    filters_applied: Dict[str, Any]
    execution_time_ms: int

class ReportResponse(BaseModel):
    metadata: ReportMetadata
    data: List[Any]
    summary: Optional[Dict[str, Any]] = None
    charts: Optional[List[Dict[str, Any]]] = None