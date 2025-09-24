from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.models.auth.user import User
from app.utils.data_exporter import DataExportService, EXPORT_FIELD_MAPPINGS
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Dynamic service mapping
SERVICE_MAPPING = {
    # Auth & User Management
    "users": {
        "service": "app.services.auth.user_service.UserService",
        "method": "get_users",
        "params": ["search"]
    },
    "roles": {
        "service": "app.services.auth.role_service.RoleService",
        "method": "get_roles",
        "params": ["search", "is_active"]
    },

    # Organization Management
    "departments": {
        "service": "app.services.organization.department_service.DepartmentService",
        "method": "get_departments",
        "params": ["search", "is_active"]
    },
    "locations": {
        "service": "app.services.organization.location_service.LocationService", 
        "method": "get_locations",
        "params": ["search", "is_active"]
    },

    # HR Management
    "employees": {
        "service": "app.services.hr.employee_service.EmployeeService", 
        "method": "get_employees",
        "params": ["search", "department_id", "location_id", "is_manager", "is_active"]
    },
    "shifts": {
        "service": "app.services.hr.shift_service.ShiftService", 
        "method": "get_shift_types",
        "params": ["is_active"]
    },
    "attendance": {
        "service": "app.services.hr.attendance_service.AttendanceService", 
        "method": "get_attendance",
        "params": ["employee_id", "start_date", "end_date", "status"]
    },
    "deduction_types": {
        "service": "app.services.hr.deduction_service.DeductionService",
        "method": "get_deduction_types",
        "params": ["is_active", "search"]
    },
    "employee_deductions": {
        "service": "app.services.hr.deduction_service.DeductionService",
        "method": "get_employee_deductions",
        "params": ["employee_id", "status", "search"]
    },
    "salaries": {
        "service": "app.services.hr.salary_service.SalaryService", 
        "method": "get_employee_salaries",
        "params": ["employee_id", "year"]
    },
    "holidays": {
        "service": "app.services.hr.holiday_service.HolidayService", 
        "method": "get_holidays",
        "params": ["year", "month", "is_active"]
    },

    # Inventory Management
    "items": {
        "service": "app.services.inventory.item_service.ItemService",
        "method": "get_items", 
        "params": ["search", "category_id", "stock_type_id", "low_stock_only"]
    },
    "categories": {
        "service": "app.services.inventory.category_service.CategoryService",
        "method": "get_categories", 
        "params": ["search"]
    },
    "stock_types": {
        "service": "app.services.inventory.stock_type_service.StockTypeService",
        "method": "get_stock_types",
        "params": ["search"]
    },
    "stock_levels": {
        "service": "app.services.inventory.stock_level_service.StockLevelService",
        "method": "get_stock_levels",
        "params": ["location_id", "item_id", "low_stock_only"]
    },
    "stock_movements": {
        "service": "app.services.inventory.stock_movement_service.StockMovementService",
        "method": "get_stock_movements",
        "params": ["item_id", "location_id", "movement_type", "start_date", "end_date"]
    },
    "reorder_requests": {
        "service": "app.services.inventory.reorder_request_service.ReorderRequestService",
        "method": "get_reorder_requests",
        "params": ["location_id", "status", "priority"]
    },
    "transfers": {
        "service": "app.services.inventory.transfer_service.TransferService",
        "method": "get_transfers",
        "params": ["from_location_id", "to_location_id", "status"]
    },
    "inventory_counts": {
        "service": "app.services.inventory.inventory_count_service.InventoryCountService",
        "method": "get_inventory_counts",
        "params": ["location_id", "status"]
    },

    # Purchase Management   
    "purchase_orders": {
        "service": "app.services.purchase.purchase_order_service.PurchaseOrderService",
        "method": "get_purchase_orders",
        "params": ["status", "supplier_id", "start_date", "end_date", "search"]
    },
    "suppliers": {
        "service": "app.services.purchase.supplier_service.SupplierService",
        "method": "get_suppliers", 
        "params": ["search", "is_active"]
    },
    "goods_receipts": {
        "service": "app.services.purchase.goods_receipt_service.GoodsReceiptService",
        "method": "get_goods_receipts", 
        "params": ["supplier_id", "purchase_order_id", "start_date", "end_date", "search"]
    },

    # Logistics Management
    "shipments": {
        "service": "app.services.logistics.shipment_service.ShipmentService",
        "method": "get_shipments",
        "params": ["search", "status", "from_location_id", "to_location_id", "driver_id", "vehicle_id", "date_from", "date_to"]
    },
    "drivers": {
        "service": "app.services.logistics.driver_service.DriverService",
        "method": "get_drivers",
        "params": ["search", "is_available", "is_active"]
    },
    "vehicles": {
        "service": "app.services.logistics.vehicle_service.VehicleService",
        "method": "get_vehicles",
        "params": ["search", "vehicle_type", "is_available", "is_active"]
    },

    # Reports
    "stock_levels_report": {
        "service": "app.services.reports.report_service.ReportService",
        "method": "get_stock_levels_report",
        "params": ["location_id", "category_id", "stock_status", "search", "sort_by", "sort_order"]
    },
    "stock_movements_report": {
        "service": "app.services.reports.report_service.ReportService",
        "method": "get_stock_movements_report",
        "params": ["from_date", "to_date", "location_id", "item_id", "movement_type", "search"]
    },
    "low_stock_alerts_report": {
        "service": "app.services.reports.report_service.ReportService",
        "method": "get_low_stock_alerts_report",
        "params": ["location_id", "category_id", "priority"]
    },
    "purchase_orders_summary_report": {
        "service": "app.services.reports.report_service.ReportService",
        "method": "get_purchase_orders_summary_report",
        "params": ["from_date", "to_date", "supplier_id", "status", "search"]
    },
    "demand_forecast_report": {
        "service": "app.services.reports.report_service.ReportService",
        "method": "get_demand_forecast_report",
        "params": ["item_id", "location_id", "forecast_period", "category_id"]
    },
    "attendance_summary_report": {
        "service": "app.services.reports.report_service.ReportService",
        "method": "get_attendance_summary_report",
        "params": ["from_date", "to_date", "department_id", "employee_id", "attendance_status"]
    },
    "salary_summary_report": {
        "service": "app.services.reports.report_service.ReportService",
        "method": "get_salary_summary_report",
        "params": ["salary_month", "department_id", "payment_status"]
    },
    "shipment_tracking_report": {
        "service": "app.services.reports.report_service.ReportService",
        "method": "get_shipment_tracking_report",
        "params": ["from_date", "to_date", "shipment_status", "driver_id", "from_location_id", "to_location_id"]
    }
}

def get_service_instance(service_path: str, session: AsyncSession):
    """Dynamically import and instantiate service"""
    try:
        module_path, class_name = service_path.rsplit('.', 1)
        module = __import__(module_path, fromlist=[class_name])
        service_class = getattr(module, class_name)
        return service_class(session)
    except Exception as e:
        logger.error(f"Error importing service {service_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service not available: {service_path}"
        )

@router.get("/{entity_type}")
async def export_data(
    entity_type: str,
    format: str = Query("excel", regex="^(csv|excel)$", description="Export format: csv or excel"),
    filename: Optional[str] = Query(None, description="Custom filename (without extension)"),
    
    # Simplified filter parameters - add more as needed
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Dynamic export endpoint that handles all entity types including reports
    """
    try:
        # Check if entity type is supported
        if entity_type not in SERVICE_MAPPING:
            available_types = ", ".join(SERVICE_MAPPING.keys())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported entity type: {entity_type}. Available: {available_types}"
            )
        
        # Check if field mapping exists
        if entity_type not in EXPORT_FIELD_MAPPINGS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Export field mapping not configured for: {entity_type}"
            )
        
        # Get service configuration
        service_config = SERVICE_MAPPING[entity_type]
        
        # Get service instance
        service = get_service_instance(service_config["service"], session)
        
        # Build parameters dynamically
        params = {
            "page_index": 1,
            "page_size": 50000  # Large number to get all data
        }
        
        # Add filters based on what the service supports
        local_vars = locals()
        for param in service_config["params"]:
            if param in local_vars and local_vars[param] is not None:
                # Convert date strings to date objects
                if param in ["start_date", "end_date", "from_date", "to_date", "salary_month"]:
                    try:
                        if local_vars[param]:
                            params[param] = datetime.strptime(local_vars[param], "%Y-%m-%d").date()
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid date format for {param}. Use YYYY-MM-DD"
                        )
                else:
                    params[param] = local_vars[param]
        
        logger.info(f"Exporting {entity_type} with params: {params}")
        
        # Get data using the service method
        method = getattr(service, service_config["method"])
        result = await method(**params)
        
        # Extract data from result
        if isinstance(result, dict) and "data" in result:
            data = result["data"]
        elif hasattr(result, 'data'):  # PaginatedResponse object
            data = result.data
        else:
            data = result if isinstance(result, list) else []
        
        logger.info(f"Retrieved {len(data)} records for export")
        
        # Prepare data for export
        exporter = DataExportService()
        export_data = exporter.prepare_data_for_export(
            data, 
            EXPORT_FIELD_MAPPINGS[entity_type]
        )
        
        logger.info(f"Prepared {len(export_data)} rows for export")
        
        # Debug: Check which columns will be summed (only for Excel exports)
        if format.lower() == "excel" and export_data:
            debug_info = exporter.debug_column_detection(export_data)
            columns_to_sum = [col for col, info in debug_info.items() if info['will_be_summed']]
            logger.info(f"Columns that will be summed: {columns_to_sum}")
            
            # Log sample values from amount columns for debugging
            for col in columns_to_sum:
                sample_values = [row.get(col, '') for row in export_data[:3]]  # First 3 rows
                logger.info(f"Sample values from '{col}': {sample_values}")
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{entity_type}_export_{timestamp}"
        
        # Export based on format
        if format.lower() == "excel":
            return exporter.export_to_excel(export_data, filename, entity_type.replace("_", " ").title())
        else:
            return exporter.export_to_csv(export_data, filename)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting {entity_type}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export {entity_type} data: {str(e)}"
        )
    