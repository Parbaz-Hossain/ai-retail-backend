# app/services/reports/report_service.py
import logging
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import distinct, select, and_, or_, func, text, desc, asc, case, cast, Integer
from sqlalchemy.orm import selectinload
from app.models.inventory.item import Item
from app.models.inventory.stock_level import StockLevel
from app.models.inventory.stock_movement import StockMovement
from app.models.inventory.category import Category
from app.models.logistics.driver import Driver
from app.models.logistics.shipment_item import ShipmentItem
from app.models.logistics.vehicle import Vehicle
from app.models.organization.location import Location
from app.models.organization.department import Department
from app.models.purchase.purchase_order import PurchaseOrder
from app.models.purchase.purchase_order_item import PurchaseOrderItem
from app.models.purchase.supplier import Supplier
from app.models.purchase.goods_receipt import GoodsReceipt
from app.models.hr.employee import Employee
from app.models.hr.attendance import Attendance
from app.models.hr.salary import Salary
from app.models.logistics.shipment import Shipment
from app.models.task.task import Task
from app.models.shared.enums import StockMovementType, PurchaseOrderStatus, AttendanceStatus, TaskStatus
from app.schemas.common.pagination import PaginatedResponse

logger = logging.getLogger(__name__)

class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # =================== INVENTORY REPORTS ===================
    
    async def get_stock_levels_report(
        self,
        page_index: int = 1,
        page_size: int = 10,
        location_id: Optional[int] = None,
        category_id: Optional[int] = None,
        stock_status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "item_name",
        sort_order: str = "asc"
    ) -> PaginatedResponse[Dict]:
        """Generate comprehensive stock levels report"""
        try:
            # Build base query
            query = select(
                StockLevel.id,
                Item.item_code.label("sku"),
                Item.name.label("item_name"),
                Category.name.label("category_name"),
                Location.name.label("location_name"),
                StockLevel.current_stock,
                StockLevel.available_stock,
                StockLevel.reserved_stock,
                StockLevel.par_level_min.label("minimum_stock"),
                StockLevel.par_level_max.label("maximum_stock"),
                Item.reorder_point,
                Item.unit_cost,
                (StockLevel.current_stock * Item.unit_cost).label("stock_value"),
                case(
                    (StockLevel.current_stock <= 0, "OUT_OF_STOCK"),
                    (StockLevel.current_stock <= Item.reorder_point, "LOW"),
                    (StockLevel.current_stock >= StockLevel.par_level_max, "HIGH"),
                    else_="NORMAL"
                ).label("stock_status"),
                case(
                    (StockLevel.current_stock <= 0, "CRITICAL"),
                    (StockLevel.current_stock <= Item.reorder_point, "HIGH"),
                    (StockLevel.current_stock <= StockLevel.par_level_min, "MEDIUM"),
                    else_="LOW"
                ).label("priority"),
                Item.unit_type.label("unit")
            ).select_from(StockLevel)\
             .join(Item, StockLevel.item_id == Item.id)\
             .join(Location, StockLevel.location_id == Location.id)\
             .outerjoin(Category, Item.category_id == Category.id)\
             .where(
                and_(
                    StockLevel.is_deleted == False,
                    Item.is_deleted == False,
                    Location.is_active == True
                )
            )

            # Apply filters
            if location_id:
                query = query.where(StockLevel.location_id == location_id)
            
            if category_id:
                query = query.where(Item.category_id == category_id)
            
            if stock_status:
                if stock_status == "LOW":
                    query = query.where(StockLevel.current_stock <= Item.reorder_point)
                elif stock_status == "OUT_OF_STOCK":
                    query = query.where(StockLevel.current_stock <= 0)
                elif stock_status == "HIGH":
                    query = query.where(StockLevel.current_stock >= StockLevel.par_level_max)
            
            if search:
                query = query.where(
                    or_(
                        Item.name.ilike(f"%{search}%"),
                        Item.item_code.ilike(f"%{search}%"),
                        Category.name.ilike(f"%{search}%"),
                        Location.name.ilike(f"%{search}%")
                    )
                )

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total_count = total_result.scalar()

            # Apply sorting
            sort_column = {
                "item_name": Item.name,
                "current_stock": StockLevel.current_stock,
                "available_stock": StockLevel.available_stock,
                "stock_value": (StockLevel.current_stock * Item.unit_cost),
                "location_name": Location.name
            }.get(sort_by, Item.name)

            if sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))

            # Apply pagination
            offset = (page_index - 1) * page_size
            query = query.offset(offset).limit(page_size)

            # Execute query
            result = await self.session.execute(query)
            rows = result.fetchall()

            # Format data
            data = []
            for idx, row in enumerate(rows):
                data.append({
                    "sl": offset + idx + 1,
                    "sku": row.sku,
                    "item_name": row.item_name,
                    "category": row.category_name or "Uncategorized",
                    "location": row.location_name,
                    "current_stock": float(row.current_stock),
                    "available_stock": float(row.available_stock),
                    "reserved_stock": float(row.reserved_stock),
                    "minimum_stock": float(row.minimum_stock or 0),
                    "maximum_stock": float(row.maximum_stock or 0),
                    "reorder_point": float(row.reorder_point or 0),
                    "unit_cost": float(row.unit_cost or 0),
                    "stock_value": float(row.stock_value or 0),
                    "stock_status": row.stock_status,
                    "priority": row.priority,
                    "unit": row.unit.value if row.unit else "PCS"
                })

            return PaginatedResponse(
                page_index=page_index,
                page_size=page_size,
                count=total_count,
                data=data
            )

        except Exception as e:
            logger.error(f"Error in stock levels report: {str(e)}")
            raise

    async def get_stock_movements_report(
        self,
        page_index: int = 1,
        page_size: int = 10,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        location_id: Optional[int] = None,
        item_id: Optional[int] = None,
        movement_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> PaginatedResponse[Dict]:
        """Generate stock movements report with detailed transaction history"""
        try:
            # Default date range (last 30 days)
            if not from_date:
                from_date = datetime.now().date() - timedelta(days=30)
            if not to_date:
                to_date = datetime.now().date()

            # Build query
            query = select(
                StockMovement.id,
                Item.item_code.label("sku"),
                Item.name.label("item_name"),
                Location.name.label("location_name"),
                StockMovement.movement_type,
                StockMovement.quantity,
                StockMovement.unit_cost,
                (StockMovement.quantity * StockMovement.unit_cost).label("total_value"),
                StockMovement.reference_type,
                StockMovement.reference_id,
                StockMovement.batch_number,
                StockMovement.expiry_date,
                StockMovement.remarks,
                StockMovement.movement_date,
                StockMovement.created_at
            ).select_from(StockMovement)\
             .join(Item, StockMovement.item_id == Item.id)\
             .join(Location, StockMovement.location_id == Location.id)\
             .where(
                and_(
                    StockMovement.is_deleted == False,
                    func.date(StockMovement.movement_date) >= from_date,
                    func.date(StockMovement.movement_date) <= to_date
                )
            )

            # Apply filters
            if location_id:
                query = query.where(StockMovement.location_id == location_id)
            
            if item_id:
                query = query.where(StockMovement.item_id == item_id)
            
            if movement_type:
                query = query.where(StockMovement.movement_type == movement_type)
            
            if search:
                query = query.where(
                    or_(
                        Item.name.ilike(f"%{search}%"),
                        Item.item_code.ilike(f"%{search}%"),
                        Location.name.ilike(f"%{search}%"),
                        StockMovement.remarks.ilike(f"%{search}%"),
                        StockMovement.batch_number.ilike(f"%{search}%")
                    )
                )

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total_count = total_result.scalar()

            # Apply pagination and sorting
            offset = (page_index - 1) * page_size
            query = query.order_by(desc(StockMovement.movement_date)).offset(offset).limit(page_size)

            # Execute query
            result = await self.session.execute(query)
            rows = result.fetchall()

            # Format data
            data = []
            for idx, row in enumerate(rows):
                data.append({
                    "sl": offset + idx + 1,
                    "sku": row.sku,
                    "item_name": row.item_name,
                    "location": row.location_name,
                    "movement_type": row.movement_type.value,
                    "quantity": float(row.quantity),
                    "unit_cost": float(row.unit_cost or 0),
                    "total_value": float(row.total_value or 0),
                    "reference_type": row.reference_type,
                    "reference_id": row.reference_id,
                    "batch_number": row.batch_number,
                    "expiry_date": row.expiry_date.isoformat() if row.expiry_date else None,
                    "remarks": row.remarks,
                    "movement_date": row.movement_date.isoformat() if row.movement_date else None,
                    "transaction_direction": "IN" if row.movement_type in [StockMovementType.INBOUND] else "OUT"
                })

            return PaginatedResponse(
                page_index=page_index,
                page_size=page_size,
                count=total_count,
                data=data
            )

        except Exception as e:
            logger.error(f"Error in stock movements report: {str(e)}")
            raise

    async def get_low_stock_alerts_report(
        self,
        page_index: int = 1,
        page_size: int = 10,
        location_id: Optional[int] = None,
        category_id: Optional[int] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "priority",
        sort_order: str = "asc"
    ) -> PaginatedResponse[Dict]:
        """Generate low stock alerts report"""
        try:
            # Build query for items below reorder point
            query = select(
                Item.item_code.label("sku"),
                Item.name.label("item_name"),
                Category.name.label("category_name"),
                Location.name.label("location_name"),
                StockLevel.current_stock,
                Item.reorder_point,
                StockLevel.par_level_min.label("minimum_stock"),
                (Item.reorder_point - StockLevel.current_stock).label("shortage_quantity"),
                case(
                    (StockLevel.current_stock <= 0, "CRITICAL"),
                    (StockLevel.current_stock <= (Item.reorder_point * 0.5), "HIGH"),
                    (StockLevel.current_stock <= Item.reorder_point, "MEDIUM"),
                    else_="LOW"
                ).label("priority"),
                Item.unit_type.label("unit"),
                Item.unit_cost,
                ((Item.reorder_point - StockLevel.current_stock) * Item.unit_cost).label("estimated_cost")
            ).select_from(StockLevel)\
             .join(Item, StockLevel.item_id == Item.id)\
             .join(Location, StockLevel.location_id == Location.id)\
             .outerjoin(Category, Item.category_id == Category.id)\
             .where(
                and_(
                    StockLevel.is_deleted == False,
                    Item.is_deleted == False,
                    Location.is_active == True,
                    StockLevel.current_stock <= Item.reorder_point
                )
            )

            # Apply filters
            if location_id:
                query = query.where(StockLevel.location_id == location_id)
            
            if category_id:
                query = query.where(Item.category_id == category_id)
            
            if priority:
                if priority == "CRITICAL":
                    query = query.where(StockLevel.current_stock <= 0)
                elif priority == "HIGH":
                    query = query.where(
                        and_(
                            StockLevel.current_stock > 0,
                            StockLevel.current_stock <= (Item.reorder_point * 0.5)
                        )
                    )

             # Enhanced search functionality
            if search:
                search_filter = or_(
                    Item.name.ilike(f"%{search}%"),
                    Item.item_code.ilike(f"%{search}%"),
                    Category.name.ilike(f"%{search}%"),
                    Location.name.ilike(f"%{search}%")
                )
                query = query.where(search_filter)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total_count = total_result.scalar()

            # Apply pagination and sorting (critical items first)
            offset = (page_index - 1) * page_size
            query = query.order_by(
                case(
                    (StockLevel.current_stock <= 0, 1),
                    (StockLevel.current_stock <= (Item.reorder_point * 0.5), 2),
                    else_=3
                ),
                StockLevel.current_stock
            ).offset(offset).limit(page_size)

            # Execute query
            result = await self.session.execute(query)
            rows = result.fetchall()

            # Format data
            data = []
            for idx, row in enumerate(rows):
                data.append({
                    "sl": offset + idx + 1,
                    "sku": row.sku,
                    "item_name": row.item_name,
                    "category": row.category_name or "Uncategorized",
                    "location": row.location_name,
                    "current_stock": float(row.current_stock),
                    "reorder_point": float(row.reorder_point or 0),
                    "minimum_stock": float(row.minimum_stock or 0),
                    "shortage_quantity": float(row.shortage_quantity),
                    "priority": row.priority,
                    "unit": row.unit.value if row.unit else "PCS",
                    "unit_cost": float(row.unit_cost or 0),
                    "estimated_reorder_cost": float(row.estimated_cost or 0),
                    "days_out_of_stock": self._calculate_days_out_of_stock(row.current_stock)
                })

            return PaginatedResponse(
                page_index=page_index,
                page_size=page_size,
                count=total_count,
                data=data
            )

        except Exception as e:
            logger.error(f"Error in low stock alerts report: {str(e)}")
            raise

    def _calculate_days_out_of_stock(self, current_stock: Decimal) -> int:
        """Calculate estimated days until out of stock based on current consumption"""
        # This is a simplified calculation - in a real system, you'd use historical movement data
        if current_stock <= 0:
            return 0
        # Placeholder logic - replace with actual consumption rate calculation
        return max(0, int(current_stock / 1))  # Assuming 1 unit per day consumption

    # =================== PURCHASE REPORTS ===================

    async def get_purchase_orders_summary_report(
        self,
        page_index: int = 1,
        page_size: int = 10,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        supplier_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> PaginatedResponse[Dict]:
        """Generate comprehensive purchase orders summary report"""
        try:
            # Default date range (last 30 days)
            if not from_date:
                from_date = datetime.now().date() - timedelta(days=30)
            if not to_date:
                to_date = datetime.now().date()

            # Build query
            query = select(
                PurchaseOrder.id,
                PurchaseOrder.po_number,
                Supplier.name.label("supplier_name"),
                PurchaseOrder.order_date,
                PurchaseOrder.expected_delivery_date,
                PurchaseOrder.status,
                PurchaseOrder.total_amount,
                PurchaseOrder.approved_date,
                func.count(PurchaseOrderItem.id).label("total_items"),
                func.sum(PurchaseOrderItem.quantity).label("total_quantity"),
                func.sum(PurchaseOrderItem.received_quantity).label("total_received"),
                case(
                    (PurchaseOrder.status == PurchaseOrderStatus.COMPLETED, "COMPLETED"),
                    (func.sum(PurchaseOrderItem.received_quantity) > 0, "PARTIAL"),
                    else_="PENDING"
                ).label("receipt_status")
            ).select_from(PurchaseOrder)\
             .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)\
             .outerjoin(PurchaseOrderItem, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)\
             .where(
                and_(
                    PurchaseOrder.is_deleted == False,
                    PurchaseOrder.order_date >= from_date,
                    PurchaseOrder.order_date <= to_date
                )
            ).group_by(
                PurchaseOrder.id,
                PurchaseOrder.po_number,
                Supplier.name,
                PurchaseOrder.order_date,
                PurchaseOrder.expected_delivery_date,
                PurchaseOrder.status,
                PurchaseOrder.total_amount,
                PurchaseOrder.approved_date
            )

            # Apply filters
            if supplier_id:
                query = query.where(PurchaseOrder.supplier_id == supplier_id)
            
            if status:
                query = query.where(PurchaseOrder.status == status)
            
            if search:
                query = query.where(
                    or_(
                        PurchaseOrder.po_number.ilike(f"%{search}%"),
                        Supplier.name.ilike(f"%{search}%"),
                        Supplier.supplier_code.ilike(f"%{search}%")
                    )
                )

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total_count = total_result.scalar()

            # Apply pagination and sorting
            offset = (page_index - 1) * page_size
            query = query.order_by(desc(PurchaseOrder.order_date)).offset(offset).limit(page_size)

            # Execute query
            result = await self.session.execute(query)
            rows = result.fetchall()

            # Format data
            data = []
            for idx, row in enumerate(rows):
                completion_percentage = 0
                if row.total_quantity and row.total_quantity > 0:
                    completion_percentage = (float(row.total_received or 0) / float(row.total_quantity)) * 100

                data.append({
                    "sl": offset + idx + 1,
                    "po_number": row.po_number,
                    "supplier_name": row.supplier_name,
                    "order_date": row.order_date.isoformat(),
                    "expected_delivery_date": row.expected_delivery_date.isoformat() if row.expected_delivery_date else None,
                    "status": row.status.value,
                    "total_amount": float(row.total_amount),
                    "total_items": row.total_items or 0,
                    "total_quantity": float(row.total_quantity or 0),
                    "total_received": float(row.total_received or 0),
                    "receipt_status": row.receipt_status,
                    "completion_percentage": round(completion_percentage, 2),
                    "approved_date": row.approved_date.isoformat() if row.approved_date else None,
                    "days_pending": (datetime.now().date() - row.order_date).days if row.status == PurchaseOrderStatus.PENDING else None
                })

            return PaginatedResponse(
                page_index=page_index,
                page_size=page_size,
                count=total_count,
                data=data
            )

        except Exception as e:
            logger.error(f"Error in purchase orders summary report: {str(e)}")
            raise

    # =================== DEMAND FORECAST REPORT ===================

    async def get_demand_forecast_report(
        self,
        page_index: int = 1,
        page_size: int = 10,
        item_id: Optional[int] = None,
        location_id: Optional[int] = None,
        forecast_period: str = "monthly",
        category_id: Optional[int] = None,
        search: Optional[str] = None,
        sort_by: str = "historical_demand",
        sort_order: str = "desc"
    ) -> PaginatedResponse[Dict]:
        """Generate AI-powered demand forecast report"""
        try:
            # This is a simplified version - in reality, you'd use ML models for forecasting
            # Build query for historical data analysis
            query = select(
                Item.item_code.label("sku"),
                Item.name.label("product_name"),
                Category.name.label("category"),
                Location.name.label("location"),
                func.sum(
                    case(
                        (StockMovement.movement_type == StockMovementType.OUTBOUND, StockMovement.quantity),
                        else_=0
                    )
                ).label("historical_demand"),
                func.avg(
                    case(
                        (StockMovement.movement_type == StockMovementType.OUTBOUND, StockMovement.quantity),
                        else_=0
                    )
                ).label("average_demand"),
                func.count(
                    case(
                        (StockMovement.movement_type == StockMovementType.OUTBOUND, 1),
                        else_=None
                    )
                ).label("transaction_count")
            ).select_from(StockMovement)\
            .join(Item, StockMovement.item_id == Item.id)\
            .join(Location, StockMovement.location_id == Location.id)\
            .outerjoin(Category, Item.category_id == Category.id)\
            .where(
                and_(
                    StockMovement.is_deleted == False,
                    StockMovement.movement_date >= datetime.now().date() - timedelta(days=90),  # Last 90 days
                    StockMovement.movement_type == StockMovementType.OUTBOUND
                )
            ).group_by(
                Item.id,
                Item.item_code,
                Item.name,
                Category.name,
                Location.id,
                Location.name
            )

            # Apply filters
            if item_id:
                query = query.where(Item.id == item_id)
            
            if location_id:
                query = query.where(Location.id == location_id)
            
            if category_id:
                query = query.where(Item.category_id == category_id)

            # Enhanced search functionality
            if search:
                search_filter = or_(
                    Item.name.ilike(f"%{search}%"),
                    Item.item_code.ilike(f"%{search}%"),
                    Category.name.ilike(f"%{search}%"),
                    Location.name.ilike(f"%{search}%")
                )
                query = query.where(search_filter)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total_count = total_result.scalar()

            # Apply pagination
            offset = (page_index - 1) * page_size
            query = query.order_by(desc("historical_demand")).offset(offset).limit(page_size)

            # Execute query
            result = await self.session.execute(query)
            rows = result.fetchall()

            # Format data with forecast calculations
            data = []
            for idx, row in enumerate(rows):
                # Simple forecasting logic (replace with actual ML model)
                historical_demand = float(row.historical_demand or 0)
                average_demand = float(row.average_demand or 0)
                
                # Calculate forecast based on period
                if forecast_period == "weekly":
                    forecast_multiplier = 1
                    planned_target = average_demand * 7
                elif forecast_period == "monthly":
                    forecast_multiplier = 4
                    planned_target = average_demand * 30
                else:  # quarterly
                    forecast_multiplier = 12
                    planned_target = average_demand * 90

                # Simple demand variation calculation
                if planned_target > 0:
                    variation_percentage = min(100, (historical_demand / planned_target) * 100)
                else:
                    variation_percentage = 0

                data.append({
                    "sl": offset + idx + 1,
                    "sku": row.sku,
                    "productName": row.product_name,
                    "category": row.category or "Uncategorized",
                    "location": row.location,
                    "forecastPeriod": forecast_period,
                    "currentSalesData": int(historical_demand),
                    "plannedSalesTarget": int(planned_target),
                    "demandVariationPercentage": round(variation_percentage, 2),
                    "averageDailyDemand": round(average_demand, 2),
                    "transactionCount": row.transaction_count or 0,
                    "forecastAccuracy": round(min(100, variation_percentage + 10), 2)  # Simulated accuracy
                })

            return PaginatedResponse(
                page_index=page_index,
                page_size=page_size,
                count=total_count,
                data=data
            )

        except Exception as e:
            logger.error(f"Error in demand forecast report: {str(e)}")
            raise

    # =================== HR ATTENDANCE REPORTS ===================

    async def get_attendance_summary_report(
        self,
        page_index: int = 1,
        page_size: int = 10,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        department_id: Optional[int] = None,
        employee_id: Optional[int] = None,
        attendance_status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "employee_name",
        sort_order: str = "asc"
    ) -> PaginatedResponse[Dict]:
        """Generate comprehensive attendance summary report"""
        try:
            # Default date range (current month)
            if not from_date:
                from_date = datetime.now().date().replace(day=1)
            if not to_date:
                to_date = datetime.now().date()

            # Build query with comprehensive attendance metrics
            query = select(
                Employee.id.label("employee_id"),
                Employee.employee_id.label("employee_code"),
                (Employee.first_name + ' ' + Employee.last_name).label("employee_name"),
                Department.name.label("department_name"),
                Location.name.label("location_name"),
                
                # Attendance counts
                func.count(Attendance.id).label("total_attendance_records"),
                func.count(
                    case((Attendance.status == AttendanceStatus.PRESENT, 1), else_=None)
                ).label("present_days"),
                func.count(
                    case((Attendance.status == AttendanceStatus.ABSENT, 1), else_=None)
                ).label("absent_days"),
                func.count(
                    case((Attendance.status == AttendanceStatus.LATE, 1), else_=None)
                ).label("late_days"),
                func.count(
                    case((Attendance.status == AttendanceStatus.LEFT_EARLY, 1), else_=None)
                ).label("early_leave_days"),
                
                # Time calculations
                func.sum(Attendance.total_hours).label("total_hours_worked"),
                func.sum(Attendance.overtime_hours).label("total_overtime_hours"),
                func.avg(Attendance.total_hours).label("avg_daily_hours"),
                func.sum(Attendance.late_minutes).label("total_late_minutes"),
                func.sum(Attendance.early_leave_minutes).label("total_early_leave_minutes"),
                
                # Working days calculation
                func.count(
                    distinct(
                        case(
                            (Attendance.is_holiday == False, Attendance.attendance_date),
                            else_=None
                        )
                    )
                ).label("total_working_days")
                
            ).select_from(Employee)\
            .join(Attendance, Employee.id == Attendance.employee_id)\
            .outerjoin(Department, Employee.department_id == Department.id)\
            .outerjoin(Location, Employee.location_id == Location.id)\
            .where(
                and_(
                    Employee.is_deleted == False,
                    Employee.is_active == True,
                    Attendance.is_deleted == False,
                    Attendance.attendance_date >= from_date,
                    Attendance.attendance_date <= to_date
                )
            ).group_by(
                Employee.id,
                Employee.employee_id,
                Employee.first_name,
                Employee.last_name,
                Department.name,
                Location.name
            )

            # Apply filters
            if department_id:
                query = query.where(Employee.department_id == department_id)
            
            if employee_id:
                query = query.where(Employee.id == employee_id)
            
            if attendance_status:
                # Filter for employees with specific attendance patterns
                if attendance_status == "POOR":
                    # Employees with attendance < 80%
                    query = query.having(
                        (func.count(case((Attendance.status == AttendanceStatus.PRESENT, 1), else_=None)) / 
                        func.count(Attendance.id) * 100) < 80
                    )
                elif attendance_status == "EXCELLENT":
                    # Employees with attendance >= 95%
                    query = query.having(
                        (func.count(case((Attendance.status == AttendanceStatus.PRESENT, 1), else_=None)) / 
                        func.count(Attendance.id) * 100) >= 95
                    )

             # Enhanced search functionality
            if search:
                search_filter = or_(
                    Employee.first_name.ilike(f"%{search}%"),
                    Employee.last_name.ilike(f"%{search}%"),
                    (Employee.first_name + ' ' + Employee.last_name).ilike(f"%{search}%"),
                    Employee.employee_id.ilike(f"%{search}%"),
                    Department.name.ilike(f"%{search}%")
                )
                query = query.where(search_filter)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total_count = total_result.scalar()

            # Apply pagination and sorting
            offset = (page_index - 1) * page_size
            query = query.order_by(Employee.first_name).offset(offset).limit(page_size)

            # Execute query
            result = await self.session.execute(query)
            rows = result.fetchall()

            # Calculate total business days in the period for accurate percentages
            business_days = self._calculate_business_days(from_date, to_date)

            # Format data
            data = []
            for idx, row in enumerate(rows):
                # Calculate attendance percentage
                attendance_percentage = 0
                if row.total_working_days > 0:
                    attendance_percentage = (row.present_days / row.total_working_days) * 100

                # Calculate punctuality percentage
                punctuality_percentage = 0
                if row.present_days > 0:
                    punctuality_percentage = ((row.present_days - row.late_days) / row.present_days) * 100

                # Determine overall status
                if attendance_percentage >= 95 and punctuality_percentage >= 90:
                    overall_status = "EXCELLENT"
                elif attendance_percentage >= 85 and punctuality_percentage >= 80:
                    overall_status = "GOOD"
                elif attendance_percentage >= 75:
                    overall_status = "AVERAGE"
                else:
                    overall_status = "NEEDS_IMPROVEMENT"

                data.append({
                    "sl": offset + idx + 1,
                    "employee_id": row.employee_id,
                    "employee_code": row.employee_code,
                    "employee_name": row.employee_name,
                    "department": row.department_name or "Not Assigned",
                    "location": row.location_name or "Not Assigned",
                    "total_working_days": business_days,
                    "present_days": row.present_days or 0,
                    "absent_days": row.absent_days or 0,
                    "late_days": row.late_days or 0,
                    "early_leave_days": row.early_leave_days or 0,
                    "attendance_percentage": round(attendance_percentage, 2),
                    "punctuality_percentage": round(punctuality_percentage, 2),
                    "total_hours_worked": round(float(row.total_hours_worked or 0), 2),
                    "overtime_hours": round(float(row.total_overtime_hours or 0), 2),
                    "average_daily_hours": round(float(row.avg_daily_hours or 0), 2),
                    "total_late_minutes": int(row.total_late_minutes or 0),
                    "total_early_leave_minutes": int(row.total_early_leave_minutes or 0),
                    "overall_status": overall_status,
                    "productivity_score": round((attendance_percentage + punctuality_percentage) / 2, 2)
                })

            return PaginatedResponse(
                page_index=page_index,
                page_size=page_size,
                count=total_count,
                data=data
            )

        except Exception as e:
            logger.error(f"Error in attendance summary report: {str(e)}")
            raise

    def _calculate_business_days(self, from_date: date, to_date: date) -> int:
        """Calculate business days between two dates"""
        try:
            current_date = from_date
            business_days = 0
            
            while current_date <= to_date:
                # Skip weekends (Saturday = 5, Sunday = 6)
                if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                    business_days += 1
                current_date += timedelta(days=1)
            
            return business_days
        except Exception:
            return (to_date - from_date).days + 1

    # =================== HR SALARY REPORTS ===================

    async def get_salary_summary_report(
        self,
        page_index: int = 1,
        page_size: int = 10,
        salary_month: Optional[date] = None,
        department_id: Optional[int] = None,
        payment_status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "employee_name",
        sort_order: str = "asc"
    ) -> PaginatedResponse[Dict]:
        """Generate comprehensive salary summary report with search - Modified for month/year matching"""
        try:
            # Default to current month if not specified
            if not salary_month:
                salary_month = datetime.now().date().replace(day=1)

            # Extract year and month from the provided date for matching
            target_year = salary_month.year
            target_month = salary_month.month

            # Build comprehensive salary query
            query = select(
                Employee.id.label("employee_id"),
                Employee.employee_id.label("employee_code"),
                (Employee.first_name + ' ' + Employee.last_name).label("employee_name"),
                Department.name.label("department_name"),
                Location.name.label("location_name"),
                Employee.position.label("designation"),
                
                # Salary components
                Salary.salary_month,
                Salary.basic_salary,
                Salary.housing_allowance,
                Salary.transport_allowance,
                Salary.overtime_amount,
                Salary.bonus,
                Salary.total_deductions,
                Salary.late_deductions,
                Salary.absent_deductions,
                Salary.other_deductions,
                Salary.gross_salary,
                Salary.net_salary,
                
                # Attendance metrics
                Salary.working_days,
                Salary.present_days,
                Salary.absent_days,
                Salary.late_days,
                
                # Payment info
                Salary.payment_status,
                Salary.payment_date,
                Salary.payment_method,
                Salary.payment_reference,
                Salary.generated_by,
                Salary.approved_by,
                Salary.created_at.label("salary_generated_at")
                
            ).select_from(Salary)\
            .join(Employee, Salary.employee_id == Employee.id)\
            .outerjoin(Department, Employee.department_id == Department.id)\
            .outerjoin(Location, Employee.location_id == Location.id)\
            .where(
                and_(
                    Salary.is_deleted == False,
                    Employee.is_deleted == False,
                    # Modified condition: Match only year and month, ignore day
                    func.extract('year', Salary.salary_month) == target_year,
                    func.extract('month', Salary.salary_month) == target_month
                )
            )

            # Apply filters
            if department_id:
                query = query.where(Employee.department_id == department_id)
            
            if payment_status:
                query = query.where(Salary.payment_status == payment_status)

            # Enhanced search functionality
            if search:
                search_filter = or_(
                    Employee.first_name.ilike(f"%{search}%"),
                    Employee.last_name.ilike(f"%{search}%"),
                    (Employee.first_name + ' ' + Employee.last_name).ilike(f"%{search}%"),
                    Employee.employee_id.ilike(f"%{search}%"),
                    Department.name.ilike(f"%{search}%"),
                    Employee.position.ilike(f"%{search}%")
                )
                query = query.where(search_filter)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total_count = total_result.scalar()

            # Apply sorting
            sort_column = {
                "employee_name": Employee.first_name,
                "net_salary": Salary.net_salary,
                "department": Department.name,
                "payment_status": Salary.payment_status,
                "designation": Employee.position,
                "gross_salary": Salary.gross_salary,
                "employee_code": Employee.employee_id
            }.get(sort_by, Employee.first_name)

            if sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))

            # Apply pagination
            offset = (page_index - 1) * page_size
            query = query.order_by(
                Employee.department_id,
                Employee.first_name
            ).offset(offset).limit(page_size)

            # Execute query
            result = await self.session.execute(query)
            rows = result.fetchall()

            # Format data
            data = []
            for idx, row in enumerate(rows):
                # Calculate efficiency metrics
                attendance_efficiency = 0
                if row.working_days > 0:
                    attendance_efficiency = (row.present_days / row.working_days) * 100

                # Calculate deduction percentage
                deduction_percentage = 0
                if row.gross_salary > 0:
                    deduction_percentage = (float(row.total_deductions) / float(row.gross_salary)) * 100

                # Determine salary status
                if row.payment_status.value == "PAID":
                    salary_status = "PAID"
                    status_color = "success"
                else:
                    # Check if overdue (more than 5 days after month end)
                    # Use the actual salary_month from database, not the input parameter
                    actual_month = row.salary_month
                    month_end = (actual_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                    if datetime.now().date() > month_end + timedelta(days=5):
                        salary_status = "OVERDUE"
                        status_color = "danger"
                    else:
                        salary_status = "PENDING"
                        status_color = "warning"

                data.append({
                    "sl": offset + idx + 1,
                    "employee_id": row.employee_code,
                    "employee_name": row.employee_name,
                    "department": row.department_name or "Not Assigned",
                    "location": row.location_name or "Not Assigned",
                    "designation": row.designation or "Not Specified",
                    "salary_month": row.salary_month.strftime("%B %Y"),  # This will show the actual month from DB
                    
                    # Salary breakdown
                    "basic_salary": float(row.basic_salary),
                    "housing_allowance": float(row.housing_allowance),
                    "transport_allowance": float(row.transport_allowance),
                    "overtime_amount": float(row.overtime_amount),
                    "bonus": float(row.bonus),
                    "gross_salary": float(row.gross_salary),
                    
                    # Deductions
                    "total_deductions": float(row.total_deductions),
                    "late_deductions": float(row.late_deductions),
                    "absent_deductions": float(row.absent_deductions),
                    "other_deductions": float(row.other_deductions),
                    "deduction_percentage": round(deduction_percentage, 2),
                    
                    # Net amount
                    "net_salary": float(row.net_salary),
                    
                    # Attendance summary
                    "working_days": row.working_days or 0,
                    "present_days": row.present_days or 0,
                    "absent_days": row.absent_days or 0,
                    "late_days": row.late_days or 0,
                    "attendance_efficiency": round(attendance_efficiency, 2),
                    
                    # Payment info
                    "payment_status": row.payment_status.value,
                    "salary_status": salary_status,
                    "status_color": status_color,
                    "payment_date": row.payment_date.strftime("%Y-%m-%d") if row.payment_date else None,
                    "payment_method": row.payment_method,
                    "payment_reference": row.payment_reference,
                    "generated_date": row.salary_generated_at.strftime("%Y-%m-%d") if row.salary_generated_at else None,
                    
                    # Performance indicators
                    "salary_efficiency_score": round((attendance_efficiency + (100 - deduction_percentage)) / 2, 2),
                    "cost_per_day": round(float(row.net_salary) / max(1, row.working_days or 1), 2)
                })

            return PaginatedResponse(
                page_index=page_index,
                page_size=page_size,
                count=total_count,
                data=data
            )

        except Exception as e:
            logger.error(f"Error in salary summary report: {str(e)}")
            raise

    # =================== LOGISTICS SHIPMENT TRACKING REPORTS ===================

    async def get_shipment_tracking_report(
        self,
        page_index: int = 1,
        page_size: int = 10,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        shipment_status: Optional[str] = None,
        driver_id: Optional[int] = None,
        from_location_id: Optional[int] = None,
        to_location_id: Optional[int] = None,
        search: Optional[str] = None,
        sort_by: str = "shipment_date",
        sort_order: str = "desc"
    ) -> PaginatedResponse[Dict]:
        """Generate comprehensive shipment tracking report"""
        try:
            # Default date range (last 30 days)
            if not from_date:
                from_date = datetime.now().date() - timedelta(days=30)
            if not to_date:
                to_date = datetime.now().date()

            # Create alias for to_location
            from sqlalchemy.orm import aliased
            ToLocation = aliased(Location, name="to_location")

            # Build comprehensive shipment query using alias
            query = select(
                Shipment.id.label("shipment_id"),
                Shipment.shipment_number,
                Shipment.shipment_date,
                Shipment.expected_delivery_date,
                Shipment.actual_delivery_date,
                Shipment.status.label("shipment_status"),
                
                # Location details
                Location.name.label("from_location"),
                ToLocation.name.label("to_location"),
                
                # Driver and vehicle details
                (Employee.first_name + ' ' + Employee.last_name).label("driver_name"),
                Employee.phone.label("driver_phone"),
                Vehicle.vehicle_number,
                Vehicle.vehicle_type,
                
                # Shipment metrics
                Shipment.distance_km,
                Shipment.fuel_cost,
                Shipment.total_weight,
                Shipment.total_volume,
                
                # Timing details
                Shipment.pickup_otp_verified,
                Shipment.delivery_otp_verified,
                Shipment.pickup_time,
                Shipment.delivery_time,
                
                # Item counts
                func.count(ShipmentItem.id).label("total_items"),
                func.sum(ShipmentItem.quantity).label("total_quantity"),
                func.sum(ShipmentItem.delivered_quantity).label("total_delivered"),
                
                # Reference and notes
                Shipment.reference_type,
                Shipment.reference_id,
                Shipment.notes
                
            ).select_from(Shipment)\
            .join(Location, Shipment.from_location_id == Location.id)\
            .join(ToLocation, Shipment.to_location_id == ToLocation.id)\
            .outerjoin(Driver, Shipment.driver_id == Driver.id)\
            .outerjoin(Employee, Driver.employee_id == Employee.id)\
            .outerjoin(Vehicle, Shipment.vehicle_id == Vehicle.id)\
            .outerjoin(ShipmentItem, Shipment.id == ShipmentItem.shipment_id)\
            .where(
                and_(
                    Shipment.is_deleted == False,
                    Shipment.shipment_date >= from_date,
                    Shipment.shipment_date <= to_date
                )
            ).group_by(
                Shipment.id,
                Location.id,
                ToLocation.id,
                Employee.id,
                Vehicle.id
            )

            # Apply filters
            if shipment_status:
                query = query.where(Shipment.status == shipment_status)
            
            if driver_id:
                query = query.where(Shipment.driver_id == driver_id)
            
            if from_location_id:
                query = query.where(Shipment.from_location_id == from_location_id)
            
            if to_location_id:
                query = query.where(Shipment.to_location_id == to_location_id)

            # Enhanced search functionality
            if search:
                search_filter = or_(
                    Shipment.shipment_number.ilike(f"%{search}%"),
                    (Employee.first_name + ' ' + Employee.last_name).ilike(f"%{search}%"),
                    Employee.first_name.ilike(f"%{search}%"),
                    Employee.last_name.ilike(f"%{search}%"),
                    Vehicle.vehicle_number.ilike(f"%{search}%"),
                    Location.name.ilike(f"%{search}%"),
                    ToLocation.name.ilike(f"%{search}%"),
                    Shipment.notes.ilike(f"%{search}%")
                )
                query = query.where(search_filter)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.session.execute(count_query)
            total_count = total_result.scalar()

            # Apply pagination and sorting
            offset = (page_index - 1) * page_size
            query = query.order_by(desc(Shipment.shipment_date)).offset(offset).limit(page_size)

            # Execute query
            result = await self.session.execute(query)
            rows = result.fetchall()

            # Format data
            data = []
            for idx, row in enumerate(rows):
                # Calculate delivery performance metrics
                delay_days = None
                delivery_performance = "PENDING"
                
                if row.actual_delivery_date and row.expected_delivery_date:
                    delay_days = (row.actual_delivery_date.date() - row.expected_delivery_date).days
                    if delay_days <= 0:
                        delivery_performance = "ON_TIME"
                    elif delay_days <= 1:
                        delivery_performance = "SLIGHTLY_DELAYED"
                    else:
                        delivery_performance = "DELAYED"
                elif row.shipment_status.value == "DELIVERED":
                    delivery_performance = "DELIVERED"
                elif row.expected_delivery_date and datetime.now().date() > row.expected_delivery_date:
                    delay_days = (datetime.now().date() - row.expected_delivery_date).days
                    delivery_performance = "OVERDUE"

                # Calculate completion percentage
                completion_percentage = 0
                if row.total_quantity and row.total_quantity > 0:
                    completion_percentage = (float(row.total_delivered or 0) / float(row.total_quantity)) * 100

                # Calculate transit time
                transit_time_hours = None
                if row.pickup_time and row.delivery_time:
                    transit_duration = row.delivery_time - row.pickup_time
                    transit_time_hours = round(transit_duration.total_seconds() / 3600, 2)

                # Determine priority/urgency
                urgency = "NORMAL"
                if row.shipment_status.value in ["READY_FOR_PICKUP", "PICKED_UP"] and delay_days and delay_days > 0:
                    urgency = "HIGH"
                elif row.shipment_status.value == "OUT_FOR_DELIVERY":
                    urgency = "MEDIUM"

                data.append({
                    "sl": offset + idx + 1,
                    "shipment_number": row.shipment_number,
                    "from_location": row.from_location,
                    "to_location": row.to_location,
                    "driver_name": row.driver_name or "Not Assigned",
                    "driver_phone": row.driver_phone,
                    "vehicle_number": row.vehicle_number or "Not Assigned",
                    "vehicle_type": row.vehicle_type,
                    
                    # Dates and timing
                    "shipment_date": row.shipment_date.strftime("%Y-%m-%d"),
                    "expected_delivery": row.expected_delivery_date.strftime("%Y-%m-%d") if row.expected_delivery_date else None,
                    "actual_delivery": row.actual_delivery_date.strftime("%Y-%m-%d %H:%M") if row.actual_delivery_date else None,
                    "pickup_time": row.pickup_time.strftime("%Y-%m-%d %H:%M") if row.pickup_time else None,
                    "delivery_time": row.delivery_time.strftime("%Y-%m-%d %H:%M") if row.delivery_time else None,
                    
                    # Status and performance
                    "status": row.shipment_status.value,
                    "delivery_performance": delivery_performance,
                    "delay_days": delay_days,
                    "urgency": urgency,
                    "transit_time_hours": transit_time_hours,
                    
                    # Shipment details
                    "total_items": row.total_items or 0,
                    "total_quantity": float(row.total_quantity or 0),
                    "total_delivered": float(row.total_delivered or 0),
                    "completion_percentage": round(completion_percentage, 2),
                    "distance_km": float(row.distance_km or 0),
                    "total_weight": float(row.total_weight or 0),
                    "total_volume": float(row.total_volume or 0),
                    "fuel_cost": float(row.fuel_cost or 0),
                    
                    # Verification status
                    "pickup_verified": row.pickup_otp_verified or False,
                    "delivery_verified": row.delivery_otp_verified or False,
                    
                    # Reference and notes
                    "reference_type": row.reference_type,
                    "reference_id": row.reference_id,
                    "notes": row.notes,
                    
                    # Calculated metrics
                    "cost_per_km": round(float(row.fuel_cost or 0) / max(1, float(row.distance_km or 1)), 2),
                    "efficiency_score": self._calculate_shipment_efficiency_score(
                        delivery_performance, completion_percentage, transit_time_hours
                    )
                })

            return PaginatedResponse(
                page_index=page_index,
                page_size=page_size,
                count=total_count,
                data=data
            )

        except Exception as e:
            logger.error(f"Error in shipment tracking report: {str(e)}")
            raise

    def _calculate_shipment_efficiency_score(self, delivery_performance: str, completion_percentage: float, transit_time_hours: Optional[float]) -> float:
        """Calculate efficiency score for shipment"""
        try:
            score = 0
            
            # Delivery performance score (40%)
            if delivery_performance == "ON_TIME":
                score += 40
            elif delivery_performance == "SLIGHTLY_DELAYED":
                score += 30
            elif delivery_performance == "DELAYED":
                score += 20
            elif delivery_performance == "DELIVERED":
                score += 35
            
            # Completion percentage score (30%)
            score += (completion_percentage / 100) * 30
            
            # Transit efficiency score (30%)
            if transit_time_hours:
                # Assume optimal transit time and score based on efficiency
                if transit_time_hours <= 4:
                    score += 30  # Excellent
                elif transit_time_hours <= 8:
                    score += 25  # Good
                elif transit_time_hours <= 12:
                    score += 20  # Average
                else:
                    score += 15  # Poor
            else:
                score += 20  # Default for incomplete data
            
            return round(score, 2)
        
        except Exception:
            return 50.0  # Default score
        