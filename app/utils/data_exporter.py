# app/utils/data_exporter.py
import csv
import pandas as pd
from io import StringIO, BytesIO
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
import logging

logger = logging.getLogger(__name__)

class DataExportService:
    def __init__(self):
        self.export_dir = Path("uploads/exports")
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    def prepare_data_for_export(self, data: List[Any], fields_mapping: Dict[str, str]) -> List[Dict[str, Any]]:
        """Prepare data for export by mapping fields and formatting"""
        exported_data = []
        
        for item in data:
            row = {}
            for field_key, display_name in fields_mapping.items():
                try:
                    # Handle nested attributes (e.g., 'department.name')
                    if '.' in field_key:
                        value = item
                        for attr in field_key.split('.'):
                            value = getattr(value, attr, None) if value else None
                    else:
                        value = getattr(item, field_key, None)
                    
                    # Format specific data types
                    if value is not None:
                        if isinstance(value, datetime):
                            value = value.strftime("%Y-%m-%d %H:%M:%S")
                        elif isinstance(value, bool):
                            value = "Yes" if value else "No"
                        elif hasattr(value, '__dict__'):  # Complex object
                            value = str(value)
                    else:
                        value = ""
                    
                    row[display_name] = value
                except Exception as e:
                    logger.warning(f"Error accessing field {field_key}: {e}")
                    row[display_name] = ""
            
            exported_data.append(row)
        
        return exported_data
    
    def export_to_csv(self, data: List[Dict[str, Any]], filename: str) -> StreamingResponse:
        """Export data to CSV format"""
        try:
            output = StringIO()
            
            if data:
                fieldnames = list(data[0].keys())
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            output.seek(0)
            
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}.csv"}
            )
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to export data to CSV"
            )
    
    def export_to_excel(self, data: List[Dict[str, Any]], filename: str, sheet_name: str = "Data") -> StreamingResponse:
        """Export data to Excel format"""
        try:
            output = BytesIO()
            
            if data:
                df = pd.DataFrame(data)
                
                # Create Excel writer with styling
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # Get workbook and worksheet for styling
                    workbook = writer.book
                    worksheet = writer.sheets[sheet_name]
                    
                    # Style headers
                    from openpyxl.styles import Font, PatternFill, Alignment
                    header_font = Font(bold=True, color="FFFFFF")
                    header_fill = PatternFill("solid", fgColor="366092")
                    header_alignment = Alignment(horizontal="center")
                    
                    for cell in worksheet[1]:  # First row (headers)
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = header_alignment
                    
                    # Auto-adjust column widths
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)
                        worksheet.column_dimensions[column_letter].width = adjusted_width
            
            output.seek(0)
            
            return StreamingResponse(
                BytesIO(output.read()),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"}
            )
            
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to export data to Excel"
            )

# Export field mappings for different entities
EXPORT_FIELD_MAPPINGS = {
    # Auth & User Management
    "users": {
        "id": "ID",
        "username": "Username", 
        "email": "Email",
        "full_name": "Full Name",
        "phone": "Phone",
        "is_active": "Active",
        "is_verified": "Verified",
        "is_superuser": "Super User",
        "created_at": "Created Date",
        "last_login": "Last Login"
    },
    "roles": {
        "id": "ID",
        "name": "Role Name",
        "description": "Description",
        "is_active": "Active",
        "is_system": "System Role",
        "created_at": "Created Date"
    },
    
    # Organization Management
    "departments": {
        "id": "ID", 
        "name": "Department Name",
        "code": "Department Code",
        "description": "Description",
        "manager_id": "Manager ID",
        "location.name": "Location",
        "is_active": "Active",
        "created_at": "Created Date"
    },
    "locations": {
        "id": "ID",
        "name": "Location Name", 
        "code": "Location Code",
        "address": "Address",
        "city": "City",
        "state": "State",
        "country": "Country",
        "postal_code": "Postal Code",
        "is_active": "Active",
        "created_at": "Created Date"
    },
    
    # HR Management
    "employees": {
        "id": "ID",
        "employee_id": "Employee ID",
        "first_name": "First Name", 
        "last_name": "Last Name",
        "email": "Email",
        "phone": "Phone",
        "position": "Position",
        "department.name": "Department",
        "location.name": "Location", 
        "hire_date": "Hire Date",
        "basic_salary": "Basic Salary",
        "is_manager": "Is Manager",
        "is_active": "Active",
        "created_at": "Created Date"
    },
    "shifts": {
        "id": "ID",
        "name": "Shift Name",
        "start_time": "Start Time",
        "end_time": "End Time", 
        "break_duration": "Break Duration",
        "location.name": "Location",
        "is_active": "Active",
        "created_at": "Created Date"
    },
    "attendance": {
        "id": "ID",
        "employee.employee_id": "Employee ID",
        "employee.first_name": "First Name",
        "employee.last_name": "Last Name",
        "date": "Date",
        "check_in_time": "Check In",
        "check_out_time": "Check Out", 
        "status": "Status",
        "total_hours": "Total Hours",
        "created_at": "Created Date"
    },
    "salaries": {
        "id": "ID",
        "employee.employee_id": "Employee ID",
        "employee.first_name": "First Name", 
        "employee.last_name": "Last Name",
        "month": "Month",
        "year": "Year",
        "basic_salary": "Basic Salary",
        "total_allowances": "Total Allowances",
        "total_deductions": "Total Deductions",
        "net_salary": "Net Salary",
        "payment_status": "Payment Status",
        "created_at": "Created Date"
    },
    "holidays": {
        "id": "ID", 
        "name": "Holiday Name",
        "date": "Date",
        "description": "Description",
        "is_recurring": "Is Recurring",
        "is_active": "Active",
        "created_at": "Created Date"
    },
    
    # Inventory Management
    "items": {
        "id": "ID",
        "item_code": "Item Code",
        "name": "Item Name",
        "description": "Description", 
        "category.name": "Category",
        "stock_type.name": "Stock Type",
        "unit_type": "Unit Type",
        "unit_cost": "Unit Cost",
        "selling_price": "Selling Price",
        "minimum_stock_level": "Min Stock Level",
        "maximum_stock_level": "Max Stock Level", 
        "reorder_point": "Reorder Point",
        "is_active": "Active",
        "created_at": "Created Date"
    },
    "categories": {
        "id": "ID",
        "name": "Category Name",
        "code": "Category Code",
        "description": "Description",
        "parent_category.name": "Parent Category",
        "is_active": "Active",
        "created_at": "Created Date"
    },
    "stock_types": {
        "id": "ID",
        "name": "Stock Type Name",
        "code": "Stock Type Code", 
        "description": "Description",
        "is_active": "Active",
        "created_at": "Created Date"
    },
    "stock_levels": {
        "id": "ID",
        "item.item_code": "Item Code",
        "item.name": "Item Name",
        "location.name": "Location",
        "current_stock": "Current Stock",
        "reserved_stock": "Reserved Stock",
        "available_stock": "Available Stock",
        "last_updated": "Last Updated"
    },
    "stock_movements": {
        "id": "ID",
        "item.item_code": "Item Code",
        "item.name": "Item Name",
        "location.name": "Location",
        "movement_type": "Movement Type",
        "quantity": "Quantity",
        "reference_number": "Reference Number",
        "notes": "Notes",
        "created_at": "Created Date"
    },
    "reorder_requests": {
        "id": "ID",
        "request_number": "Request Number",
        "location.name": "Location", 
        "status": "Status",
        "requested_by.full_name": "Requested By",
        "approved_by.full_name": "Approved By",
        "total_items": "Total Items",
        "created_at": "Created Date"
    },
    "transfers": {
        "id": "ID",
        "transfer_number": "Transfer Number",
        "from_location.name": "From Location",
        "to_location.name": "To Location",
        "status": "Status",
        "requested_by.full_name": "Requested By",
        "total_items": "Total Items",
        "created_at": "Created Date"
    },
    "inventory_counts": {
        "id": "ID",
        "count_number": "Count Number",
        "location.name": "Location",
        "status": "Status", 
        "counted_by.full_name": "Counted By",
        "total_items": "Total Items",
        "discrepancies": "Discrepancies",
        "created_at": "Created Date"
    },
    
    # Purchase Management
    "purchase_orders": {
        "id": "ID",
        "po_number": "PO Number",
        "supplier.name": "Supplier",
        "status": "Status",
        "order_date": "Order Date",
        "expected_delivery_date": "Expected Delivery",
        "total_amount": "Total Amount",
        "created_by.full_name": "Created By",
        "created_at": "Created Date"
    },
    "suppliers": {
        "id": "ID",
        "name": "Supplier Name",
        "code": "Supplier Code",
        "contact_person": "Contact Person",
        "email": "Email",
        "phone": "Phone", 
        "address": "Address",
        "city": "City",
        "country": "Country",
        "is_active": "Active",
        "created_at": "Created Date"
    },
    "goods_receipts": {
        "id": "ID",
        "receipt_number": "Receipt Number",
        "purchase_order.po_number": "PO Number",
        "supplier.name": "Supplier",
        "received_date": "Received Date",
        "total_items": "Total Items",
        "received_by.full_name": "Received By",
        "created_at": "Created Date"
    },
    
    # Logistics Management  
    "shipments": {
        "id": "ID",
        "shipment_number": "Shipment Number",
        "from_location.name": "From Location",
        "to_location.name": "To Location",
        "status": "Status",
        "driver.name": "Driver",
        "vehicle.license_plate": "Vehicle",
        "scheduled_date": "Scheduled Date",
        "created_at": "Created Date"
    },
    "drivers": {
        "id": "ID",
        "name": "Driver Name",
        "license_number": "License Number",
        "phone": "Phone",
        "email": "Email",
        "is_active": "Active",
        "created_at": "Created Date"
    },
    "vehicles": {
        "id": "ID", 
        "license_plate": "License Plate",
        "make": "Make",
        "model": "Model",
        "year": "Year",
        "capacity": "Capacity",
        "is_active": "Active",
        "created_at": "Created Date"
    }
}
