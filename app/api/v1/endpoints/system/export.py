# app/api/v1/endpoints/common/export.py - Single Dynamic Export Endpoint

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.models.auth.user import User
from app.utils.data_exporter import DataExportService, EXPORT_FIELD_MAPPINGS
from typing import Optional, Dict, Any
from datetime import datetime
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
        "service": "app.services.hr.employee_service.EmployeeService", 
        "method": "get_employees",
        "params": ["search", "department_id", "location_id", "is_manager", "is_active"]
    },
    "attendance": {
        "service": "app.services.hr.employee_service.EmployeeService", 
        "method": "get_employees",
        "params": ["search", "department_id", "location_id", "is_manager", "is_active"]
    },
    "salaries": {
        "service": "app.services.hr.employee_service.EmployeeService", 
        "method": "get_employees",
        "params": ["search", "department_id", "location_id", "is_manager", "is_active"]
    },
    "holidays": {
        "service": "app.services.hr.employee_service.EmployeeService", 
        "method": "get_employees",
        "params": ["search", "department_id", "location_id", "is_manager", "is_active"]
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
        "params": ["search", "is_active"]
    },
     "stock_types": {
        "service": "app.services.inventory.stock_level_service.StockLevelService",
        "method": "get_stock_levels",
        "params": ["location_id", "item_id", "search"]
    },
    "stock_levels": {
        "service": "app.services.inventory.stock_level_service.StockLevelService",
        "method": "get_stock_levels",
        "params": ["location_id", "item_id", "search"]
    },
     "stock_movements": {
        "service": "app.services.inventory.stock_level_service.StockLevelService",
        "method": "get_stock_levels",
        "params": ["location_id", "item_id", "search"]
    },
     "reorder_requests": {
        "service": "app.services.inventory.stock_level_service.StockLevelService",
        "method": "get_stock_levels",
        "params": ["location_id", "item_id", "search"]
    },
    
     "transfers": {
        "service": "app.services.inventory.stock_level_service.StockLevelService",
        "method": "get_stock_levels",
        "params": ["location_id", "item_id", "search"]
    },
     "inventory_counts": {
        "service": "app.services.inventory.stock_level_service.StockLevelService",
        "method": "get_stock_levels",
        "params": ["location_id", "item_id", "search"]
    },

    # Purchase Management   
    "purchase_orders": {
        "service": "app.services.purchase.purchase_order_service.PurchaseOrderService",
        "method": "get_purchase_orders",
        "params": ["search", "status", "supplier_id"]
    },
    "suppliers": {
        "service": "app.services.purchase.supplier_service.SupplierService",
        "method": "get_suppliers", 
        "params": ["search", "is_active"]
    },
    "goods_receipts": {
        "service": "app.services.purchase.supplier_service.SupplierService",
        "method": "get_suppliers", 
        "params": ["search", "is_active"]
    },

    # Logistics Management
    "shipments": {
        "service": "app.services.logistics.shipment_service.ShipmentService",
        "method": "get_shipments",
        "params": ["search", "status"]
    },
     "shipments": {
        "service": "app.services.logistics.shipment_service.ShipmentService",
        "method": "get_shipments",
        "params": ["search", "status"]
    },
     "drivers": {
        "service": "app.services.logistics.shipment_service.ShipmentService",
        "method": "get_shipments",
        "params": ["search", "status"]
    },
     "vehicles": {
        "service": "app.services.logistics.shipment_service.ShipmentService",
        "method": "get_shipments",
        "params": ["search", "status"]
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
    format: str = Query("csv", regex="^(csv|excel)$", description="Export format: csv or excel"),
    filename: Optional[str] = Query(None, description="Custom filename (without extension)"),
    
    # Common filters
    search: Optional[str] = Query(None, description="Search term"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    
    # Entity-specific filters
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    location_id: Optional[int] = Query(None, description="Filter by location ID"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    supplier_id: Optional[int] = Query(None, description="Filter by supplier ID"),
    item_id: Optional[int] = Query(None, description="Filter by item ID"),
    stock_type_id: Optional[int] = Query(None, description="Filter by stock type ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_manager: Optional[bool] = Query(None, description="Filter by manager status"),
    low_stock_only: Optional[bool] = Query(None, description="Show only low stock items"),
    
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Dynamic export endpoint that handles all entity types
    
    Supported entity types:
    - users, employees, items, roles, departments, locations
    - categories, stock_levels, purchase_orders, suppliers
    - shipments, tasks, and more...
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
                params[param] = local_vars[param]
        
        # Get data using the service method
        method = getattr(service, service_config["method"])
        result = await method(**params)
        
        # Extract data from result
        if isinstance(result, dict) and "data" in result:
            data = result["data"]
        else:
            data = result if isinstance(result, list) else []
        
        # Prepare data for export
        exporter = DataExportService()
        export_data = exporter.prepare_data_for_export(
            data, 
            EXPORT_FIELD_MAPPINGS[entity_type]
        )
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{entity_type}_export_{timestamp}"
        
        # Export based on format
        if format.lower() == "excel":
            return exporter.export_to_excel(export_data, filename, entity_type.title())
        else:
            return exporter.export_to_csv(export_data, filename)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting {entity_type}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export {entity_type} data: {str(e)}"
        )