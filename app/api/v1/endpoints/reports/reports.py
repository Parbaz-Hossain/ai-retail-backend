from typing import Optional, Dict
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.schemas.common.pagination import PaginatedResponseNew
from app.services.reports.report_service import ReportService

router = APIRouter()

# =================== INVENTORY REPORTS ===================

@router.get("/inventory/stock-levels", response_model=PaginatedResponseNew[Dict])
async def get_stock_levels_report(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    location_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),
    stock_status: Optional[str] = Query(None),  # LOW, NORMAL, HIGH, OUT_OF_STOCK
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("item_name"),  # item_name, current_stock, available_stock
    sort_order: Optional[str] = Query("asc"),  # asc, desc
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Stock Levels Report with filtering
    Shows current stock status for all items across locations
    """
    try:
        report_service = ReportService(session)
        result = await report_service.get_stock_levels_report(
            page_index=page_index,
            page_size=page_size,
            location_id=location_id,
            category_id=category_id,
            stock_status=stock_status,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate stock levels report: {str(e)}"
        )

@router.get("/inventory/stock-movements", response_model=PaginatedResponseNew[Dict])
async def get_stock_movements_report(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    location_id: Optional[int] = Query(None),
    item_id: Optional[int] = Query(None),
    movement_type: Optional[str] = Query(None),  # INBOUND, OUTBOUND, TRANSFER, etc.
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Stock Movements Report
    Tracks all inventory movements with detailed analysis
    """
    try:
        report_service = ReportService(session)
        result = await report_service.get_stock_movements_report(
            page_index=page_index,
            page_size=page_size,
            from_date=from_date,
            to_date=to_date,
            location_id=location_id,
            item_id=item_id,
            movement_type=movement_type,
            search=search
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate stock movements report: {str(e)}"
        )

@router.get("/inventory/low-stock-alerts", response_model=PaginatedResponseNew[Dict])
async def get_low_stock_alerts_report(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    location_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),  # CRITICAL, HIGH, MEDIUM, LOW
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Low Stock Alerts Report
    Items that need immediate attention for reordering
    """
    try:
        report_service = ReportService(session)
        result = await report_service.get_low_stock_alerts_report(
            page_index=page_index,
            page_size=page_size,
            location_id=location_id,
            category_id=category_id,
            priority=priority
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate low stock alerts report: {str(e)}"
        )

# =================== PURCHASE REPORTS ===================

@router.get("/purchase/purchase-orders-summary", response_model=PaginatedResponseNew[Dict])
async def get_purchase_orders_summary_report(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    supplier_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),  # DRAFT, PENDING, APPROVED, etc.
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Purchase Orders Summary Report
    Complete overview of purchase order activities
    """
    try:
        report_service = ReportService(session)
        result = await report_service.get_purchase_orders_summary_report(
            page_index=page_index,
            page_size=page_size,
            from_date=from_date,
            to_date=to_date,
            supplier_id=supplier_id,
            status=status,
            search=search
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate purchase orders summary report: {str(e)}"
        )

# =================== HR REPORTS ===================

@router.get("/hr/attendance-summary", response_model=PaginatedResponseNew[Dict])
async def get_attendance_summary_report(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    department_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    attendance_status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Employee Attendance Summary Report
    Track attendance patterns and compliance
    """
    try:
        report_service = ReportService(session)
        result = await report_service.get_attendance_summary_report(
            page_index=page_index,
            page_size=page_size,
            from_date=from_date,
            to_date=to_date,
            department_id=department_id,
            employee_id=employee_id,
            attendance_status=attendance_status
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate attendance summary report: {str(e)}"
        )

@router.get("/hr/salary-summary", response_model=PaginatedResponseNew[Dict])
async def get_salary_summary_report(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    salary_month: Optional[date] = Query(None),
    department_id: Optional[int] = Query(None),
    payment_status: Optional[str] = Query(None),  # PAID, UNPAID
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Salary Summary Report
    Overview of salary payments and pending amounts
    """
    try:
        report_service = ReportService(session)
        result = await report_service.get_salary_summary_report(
            page_index=page_index,
            page_size=page_size,
            salary_month=salary_month,
            department_id=department_id,
            payment_status=payment_status
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate salary summary report: {str(e)}"
        )

# =================== LOGISTICS REPORTS ===================

@router.get("/logistics/shipment-tracking", response_model=PaginatedResponseNew[Dict])
async def get_shipment_tracking_report(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    shipment_status: Optional[str] = Query(None),
    driver_id: Optional[int] = Query(None),
    from_location_id: Optional[int] = Query(None),
    to_location_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Shipment Tracking Report
    Monitor shipment status and delivery performance
    """
    try:
        report_service = ReportService(session)
        result = await report_service.get_shipment_tracking_report(
            page_index=page_index,
            page_size=page_size,
            from_date=from_date,
            to_date=to_date,
            shipment_status=shipment_status,
            driver_id=driver_id,
            from_location_id=from_location_id,
            to_location_id=to_location_id
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate shipment tracking report: {str(e)}"
        )

# =================== ANALYTICS & INSIGHTS ===================

@router.get("/analytics/demand-forecast", response_model=PaginatedResponseNew[Dict])
async def get_demand_forecast_report(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    item_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    forecast_period: Optional[str] = Query("monthly"),  # weekly, monthly, quarterly
    category_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    AI-Powered Demand Forecast Report
    Predictive analytics for inventory planning
    """
    try:
        report_service = ReportService(session)
        result = await report_service.get_demand_forecast_report(
            page_index=page_index,
            page_size=page_size,
            item_id=item_id,
            location_id=location_id,
            forecast_period=forecast_period,
            category_id=category_id
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate demand forecast report: {str(e)}"
        )

# =================== EXPORT & SCHEDULING ===================
# region EXPORT & SCHEDULING
# @router.post("/export/schedule-report")
# async def schedule_report_export(
#     report_type: str,
#     schedule_frequency: str = "daily",  # daily, weekly, monthly
#     export_format: str = "excel",       # excel, csv, pdf
#     email_recipients: List[str] = [],
#     filters: Dict[str, Any] = {},
#     session: AsyncSession = Depends(get_async_session),
#     current_user = Depends(get_current_user)
# ):
#     """
#     Schedule Automated Report Generation
#     Set up recurring report generation and distribution
#     """
#     try:
#         report_service = AdvancedReportService(session)
#         result = await report_service.schedule_report_export(
#             report_type=report_type,
#             schedule_frequency=schedule_frequency,
#             export_format=export_format,
#             email_recipients=email_recipients,
#             filters=filters,
#             user_id=current_user.id
#         )
#         return result
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to schedule report export: {str(e)}"
#         )

# @router.get("/export/download-report/{export_id}")
# async def download_report(
#     export_id: str,
#     session: AsyncSession = Depends(get_async_session),
#     current_user = Depends(get_current_user)
# ):
#     """
#     Download Generated Report
#     Retrieve previously generated report files
#     """
#     try:
#         report_service = AdvancedReportService(session)
#         result = await report_service.download_report(
#             export_id=export_id,
#             user_id=current_user.id
#         )
#         return result
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to download report: {str(e)}"
#         )
# endregion