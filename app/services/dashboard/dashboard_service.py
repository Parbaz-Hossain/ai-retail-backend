import logging
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, extract, desc

from app.models.purchase.purchase_order import PurchaseOrder
from app.models.hr.employee import Employee
from app.models.hr.attendance import Attendance
from app.models.hr.salary import Salary
from app.models.hr.shift_type import ShiftType
from app.models.hr.holiday import Holiday
from app.models.inventory.item import Item
from app.models.inventory.stock_level import StockLevel
from app.models.inventory.reorder_request import ReorderRequest
from app.models.logistics.vehicle import Vehicle
from app.models.logistics.driver import Driver
from app.models.logistics.shipment import Shipment
from app.models.shared.enums import (
    PurchaseOrderStatus, AttendanceStatus, SalaryPaymentStatus,
    ReorderRequestStatus, ShipmentStatus
)
from app.schemas.dashboard.dashboard_schema import DashboardResponse

logger = logging.getLogger(__name__)

class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_dashboard_data(self) -> DashboardResponse:
        """Get complete dashboard data"""
        try:
            today = date.today()
            
            # Get all metrics concurrently
            purchase_metrics = await self._get_purchase_metrics(today)
            employee_metrics = await self._get_employee_metrics(today)
            stock_metrics = await self._get_stock_metrics()
            salary_metrics = await self._get_salary_metrics()
            po_approvals = await self._get_po_approvals()
            shift_info = await self._get_shift_info(today)
            reorder_metrics = await self._get_reorder_metrics()
            holiday_info = await self._get_holiday_info(today)

            return DashboardResponse(
                purchase_metrics=purchase_metrics,
                employee_metrics=employee_metrics,
                stock_metrics=stock_metrics,
                salary_metrics=salary_metrics,
                po_approvals=po_approvals,
                shift_info=shift_info,
                reorder_metrics=reorder_metrics,
                holiday_info=holiday_info
            )

        except Exception as e:
            logger.error(f"Error getting dashboard data: {str(e)}")
            raise

    async def _get_purchase_metrics(self, today: date) -> Dict[str, Any]:
        """Get purchase-related metrics"""
        try:
            # Today's purchases
            today_purchase_result = await self.session.execute(
                select(func.coalesce(func.sum(PurchaseOrder.total_amount), 0))
                .where(
                    and_(
                        PurchaseOrder.order_date == today,
                        PurchaseOrder.is_deleted == False
                    )
                )
            )
            today_purchase = float(today_purchase_result.scalar())

            # Total purchase orders
            total_po_result = await self.session.execute(
                select(func.count(PurchaseOrder.id))
                .where(PurchaseOrder.is_deleted == False)
            )
            total_purchase_orders = total_po_result.scalar()

            # Pending approvals
            pending_approvals_result = await self.session.execute(
                select(func.count(PurchaseOrder.id))
                .where(
                    and_(
                        PurchaseOrder.status == PurchaseOrderStatus.PENDING,
                        PurchaseOrder.is_deleted == False
                    )
                )
            )
            pending_approvals = pending_approvals_result.scalar()

            return {
                "today_purchase": today_purchase,
                "total_purchase_orders": total_purchase_orders,
                "pending_approvals": pending_approvals
            }

        except Exception as e:
            logger.error(f"Error getting purchase metrics: {str(e)}")
            return {"today_purchase": 0, "total_purchase_orders": 0, "pending_approvals": 0}

    async def get_purchase_report(self) -> Dict[str, Any]:
        """Get purchase report data"""
        try:
            today = date.today()
            # Total purchases of last 12 months
            last_12_months = [
                today.replace(day=1) - timedelta(days=30 * i)
                for i in range(12)
            ]
            total_purchase = 0.0
            monthly_data = []

            for month_date in reversed(last_12_months):
                month_result = await self.session.execute(
                    select(func.coalesce(func.sum(PurchaseOrder.total_amount), 0))
                    .where(
                        and_(
                            extract('year', PurchaseOrder.order_date) == month_date.year,
                            extract('month', PurchaseOrder.order_date) == month_date.month,
                            PurchaseOrder.is_deleted == False
                        )
                    )
                )
                month_total = float(month_result.scalar())
                total_purchase += month_total
                monthly_data.append({
                    "month": month_date.strftime("%b"),
                    "value": month_total
                })

            return {
                "total_purchase": total_purchase,
                "monthly_purchase_data": monthly_data
            }

        except Exception as e:
            logger.error(f"Error getting purchase report: {str(e)}")
            return {"total_purchase": 0, "monthly_purchase_data": []}

    async def _get_employee_metrics(self, today: date) -> Dict[str, Any]:
        """Get employee-related metrics"""
        try:
            # Total and active employees
            total_employees_result = await self.session.execute(
                select(func.count(Employee.id))
                .where(Employee.is_deleted == False)
            )
            total_employees = total_employees_result.scalar()

            active_employees_result = await self.session.execute(
                select(func.count(Employee.id))
                .where(
                    and_(
                        Employee.is_active == True,
                        Employee.is_deleted == False
                    )
                )
            )
            active_employees = active_employees_result.scalar()

            return {
                "active_employees": active_employees,
                "total_employees": total_employees
            }

        except Exception as e:
            logger.error(f"Error getting employee metrics: {str(e)}")
            return {"active_employees": 0, "total_employees": 0}

    async def get_employee_report(self, today: date) -> Dict[str, Any]:
        """Get employee-related metrics"""
        try:
            # Today's attendance
            on_duty_result = await self.session.execute(
                select(func.count(Attendance.id))
                .where(
                    and_(
                        Attendance.attendance_date == today,
                        Attendance.status == AttendanceStatus.PRESENT
                    )
                )
            )
            on_duty_today = on_duty_result.scalar()

            # Staff status for today
            staff_status_result = await self.session.execute(
                select(Employee, Attendance)
                .outerjoin(
                    Attendance,
                    and_(
                        Employee.id == Attendance.employee_id,
                        Attendance.attendance_date == today
                    )
                )
                .where(
                    and_(
                        Employee.is_active == True,
                        Employee.is_deleted == False
                    )
                )
                .limit(10)
            )

            staff_status = []
            for employee, attendance in staff_status_result:
                status = "Not Checked"
                if attendance:
                    if attendance.status == AttendanceStatus.PRESENT:
                        status = "Checked In"
                    elif attendance.status == AttendanceStatus.LATE:
                        status = "Late"
                    elif attendance.status == AttendanceStatus.ABSENT:
                        status = "Absent"

                staff_status.append({
                    "name": f"{employee.first_name} {employee.last_name}",
                    "status": status,
                    "employee_id": employee.employee_id,
                    "profile_image": employee.profile_image
                })

            return {
                "on_duty_today": on_duty_today,
                "staff_status": staff_status
            }

        except Exception as e:
            logger.error(f"Error getting employee report: {str(e)}")
            return {"on_duty_today": 0, "staff_status": []}

    async def _get_stock_metrics(self) -> Dict[str, Any]:
        """Get stock-related metrics"""
        try:
            # Total items
            total_items_result = await self.session.execute(
                select(func.count(Item.id))
                .where(
                    and_(
                        Item.is_active == True,
                        Item.is_deleted == False
                    )
                )
            )
            total_items = total_items_result.scalar()

            # Low stock items (current stock <= reorder point)
            low_stock_result = await self.session.execute(
                select(func.count(StockLevel.id))
                .join(Item)
                .where(
                    and_(
                        StockLevel.current_stock <= Item.reorder_point,
                        Item.is_active == True,
                        StockLevel.is_deleted == False
                    )
                )
            )
            low_stock_items = low_stock_result.scalar()

            return {
                "low_stock_items": low_stock_items,
                "total_items": total_items
            }

        except Exception as e:
            logger.error(f"Error getting stock metrics: {str(e)}")
            return {"low_stock_items": 0, "total_items": 0}

    async def get_item_availability_report(self) -> Dict[str, Any]:
        """Get item availability report"""
        try:          
            # Item availability by category (sample data)
            availability_result = await self.session.execute(
                select(
                    func.coalesce(Item.name, 'Unknown'),
                    func.sum(StockLevel.current_stock)
                )
                .select_from(Item)
                .outerjoin(StockLevel)
                .where(Item.is_active == True)
                .group_by(Item.name)
                .limit(7)
            )

            item_availability = []
            for item_name, stock_qty in availability_result:
                item_availability.append({
                    "item": item_name,
                    "quantity": float(stock_qty or 0)
                })

            return {
                "item_availability": item_availability
            }

        except Exception as e:
            logger.error(f"Error getting item availability report: {str(e)}")
            return {"item_availability": []}

    async def _get_salary_metrics(self) -> Dict[str, Any]:
        """Get salary-related metrics"""
        try:
            # Get last month (for salary generation)
            today = date.today()
            if today.month == 1:
                last_month = today.replace(year=today.year - 1, month=12, day=1)
            else:
                last_month = today.replace(month=today.month - 1, day=1)

            # Individual salary details for last month
            individual_result = await self.session.execute(
                select(Salary, Employee)
                .join(Employee)
                .where(
                    extract('year', Salary.salary_month) == last_month.year,
                    extract('month', Salary.salary_month) == last_month.month
                )
                .limit(6)
            )

            individual_salaries = []
            for salary, employee in individual_result:
                individual_salaries.append({
                    "name": f"{employee.first_name} {employee.last_name}",
                    "amount": float(salary.net_salary),
                    "status": salary.payment_status.value,
                    "profile_image": employee.profile_image
                })

            return {
                "individual_salaries": individual_salaries
            }

        except Exception as e:
            logger.error(f"Error getting salary metrics: {str(e)}")
            return {"total_salary_paid": 0, "pending_salaries": 0, "individual_salaries": []}

    async def _get_vehicle_metrics(self) -> Dict[str, Any]:
        """Get vehicle-related metrics"""
        try:
            # Vehicle status counts
            available_result = await self.session.execute(
                select(func.count(Vehicle.id))
                .where(
                    and_(
                        Vehicle.is_available == True,
                        Vehicle.is_active == True,
                        Vehicle.is_deleted == False
                    )
                )
            )
            available_vehicles = available_result.scalar()

            not_available_result = await self.session.execute(
                select(func.count(Vehicle.id))
                .where(
                    and_(
                        Vehicle.is_available == False,
                        Vehicle.is_active == True,
                        Vehicle.is_deleted == False
                    )
                )
            )
            not_available_vehicles = not_available_result.scalar()

            # Engaged vehicles (vehicles currently in shipments)
            engaged_result = await self.session.execute(
                select(func.count(func.distinct(Shipment.vehicle_id)))
                .where(
                    Shipment.status.in_([
                        ShipmentStatus.PICKED_UP,
                        ShipmentStatus.IN_TRANSIT,
                        ShipmentStatus.OUT_FOR_DELIVERY
                    ])
                )
            )
            engaged_vehicles = engaged_result.scalar()

            # Vehicle status details
            vehicle_status_result = await self.session.execute(
                select(Vehicle)
                .where(
                    and_(
                        Vehicle.is_active == True,
                        Vehicle.is_deleted == False
                    )
                )
                .limit(4)
            )

            vehicle_status = []
            for vehicle in vehicle_status_result.scalars():
                status = "Available" if vehicle.is_available else "Not Available"
                
                # Check if vehicle is currently engaged
                engaged_check = await self.session.execute(
                    select(Shipment.id)
                    .where(
                        and_(
                            Shipment.vehicle_id == vehicle.id,
                            Shipment.status.in_([
                                ShipmentStatus.PICKED_UP,
                                ShipmentStatus.IN_TRANSIT,
                                ShipmentStatus.OUT_FOR_DELIVERY
                            ])
                        )
                    )
                )
                if engaged_check.scalar():
                    status = "Engage"

                vehicle_status.append({
                    "vehicle_number": vehicle.vehicle_number,
                    "status": status,
                    "type": vehicle.vehicle_type
                })

            return {
                "available_vehicles": available_vehicles,
                "engaged_vehicles": engaged_vehicles,
                "not_available_vehicles": not_available_vehicles,
                "vehicle_status": vehicle_status
            }

        except Exception as e:
            logger.error(f"Error getting vehicle metrics: {str(e)}")
            return {"available_vehicles": 0, "engaged_vehicles": 0, "not_available_vehicles": 0, "vehicle_status": []}

    async def _get_driver_metrics(self) -> Dict[str, Any]:
        """Get driver-related metrics"""
        try:
            # Driver availability counts
            available_result = await self.session.execute(
                select(func.count(Driver.id))
                .where(
                    and_(
                        Driver.is_available == True,
                        Driver.is_active == True,
                        Driver.is_deleted == False
                    )
                )
            )
            available_drivers = available_result.scalar()

            not_available_result = await self.session.execute(
                select(func.count(Driver.id))
                .where(
                    and_(
                        Driver.is_available == False,
                        Driver.is_active == True,
                        Driver.is_deleted == False
                    )
                )
            )
            not_available_drivers = not_available_result.scalar()

            # Engaged drivers
            engaged_result = await self.session.execute(
                select(func.count(func.distinct(Shipment.driver_id)))
                .where(
                    Shipment.status.in_([
                        ShipmentStatus.PICKED_UP,
                        ShipmentStatus.IN_TRANSIT,
                        ShipmentStatus.OUT_FOR_DELIVERY
                    ])
                )
            )
            engaged_drivers = engaged_result.scalar()

            # Driver status details
            driver_status_result = await self.session.execute(
                select(Driver, Employee)
                .join(Employee)
                .where(
                    and_(
                        Driver.is_active == True,
                        Driver.is_deleted == False
                    )
                )
                .limit(5)
            )

            driver_status = []
            for driver, employee in driver_status_result:
                status = "Available" if driver.is_available else "Not Available"
                
                # Check if driver is currently engaged
                engaged_check = await self.session.execute(
                    select(Shipment.id)
                    .where(
                        and_(
                            Shipment.driver_id == driver.id,
                            Shipment.status.in_([
                                ShipmentStatus.PICKED_UP,
                                ShipmentStatus.IN_TRANSIT,
                                ShipmentStatus.OUT_FOR_DELIVERY
                            ])
                        )
                    )
                )
                if engaged_check.scalar():
                    status = "Engage"

                driver_status.append({
                    "name": f"{employee.first_name} {employee.last_name}",
                    "status": status,
                    "license_number": driver.license_number
                })

            return {
                "available_drivers": available_drivers,
                "engaged_drivers": engaged_drivers,
                "not_available_drivers": not_available_drivers,
                "driver_status": driver_status
            }

        except Exception as e:
            logger.error(f"Error getting driver metrics: {str(e)}")
            return {"available_drivers": 0, "engaged_drivers": 0, "not_available_drivers": 0, "driver_status": []}

    async def _get_shift_info(self, today: date) -> Dict[str, Any]:
        """Get current and next shift information"""
        try:
            current_time = datetime.now().time()
            
            # Get current shift
            current_shift_result = await self.session.execute(
                select(ShiftType)
                .where(
                    and_(
                        ShiftType.start_time <= current_time,
                        ShiftType.end_time >= current_time,
                        ShiftType.is_active == True
                    )
                )
                .limit(1)
            )
            current_shift = current_shift_result.scalar_one_or_none()

            # Get next shift (simple logic - get the next shift by start time)
            next_shift_result = await self.session.execute(
                select(ShiftType)
                .where(
                    and_(
                        ShiftType.start_time > current_time,
                        ShiftType.is_active == True
                    )
                )
                .order_by(ShiftType.start_time)
                .limit(1)
            )
            next_shift = next_shift_result.scalar_one_or_none()

            # If no next shift found, get the first shift of next day
            if not next_shift:
                next_shift_result = await self.session.execute(
                    select(ShiftType)
                    .where(ShiftType.is_active == True)
                    .order_by(ShiftType.start_time)
                    .limit(1)
                )
                next_shift = next_shift_result.scalar_one_or_none()

            return {
                "current_shift": {
                    "name": current_shift.name if current_shift else "No Active Shift",
                    "start_time": str(current_shift.start_time) if current_shift else None,
                    "end_time": str(current_shift.end_time) if current_shift else None
                } if current_shift else None,
                "next_shift": {
                    "name": next_shift.name if next_shift else "No Next Shift",
                    "start_time": str(next_shift.start_time) if next_shift else None,
                    "end_time": str(next_shift.end_time) if next_shift else None
                } if next_shift else None
            }

        except Exception as e:
            logger.error(f"Error getting shift info: {str(e)}")
            return {"current_shift": None, "next_shift": None}

    async def _get_attendance_metrics(self, today: date) -> Dict[str, Any]:
        """Get daily present and absent count for current month"""
        try:
            first_day = today.replace(day=1)
            # Get last day of current month
            if first_day.month == 12:
                next_month = first_day.replace(year=first_day.year + 1, month=1, day=1)
            else:
                next_month = first_day.replace(month=first_day.month + 1, day=1)
            last_day = next_month - timedelta(days=1)

            num_days = (last_day - first_day).days + 1
            daily_attendance = []

            for i in range(num_days):
                day = first_day + timedelta(days=i)
                present_result = await self.session.execute(
                    select(func.count(Attendance.id))
                    .where(
                        and_(
                            Attendance.attendance_date == day,
                            Attendance.status == AttendanceStatus.PRESENT
                        )
                    )
                )
                present_count = present_result.scalar()

                absent_result = await self.session.execute(
                    select(func.count(Attendance.id))
                    .where(
                        and_(
                            Attendance.attendance_date == day,
                            Attendance.status == AttendanceStatus.ABSENT
                        )
                    )
                )
                absent_count = absent_result.scalar()

                daily_attendance.append({
                    "date": day.strftime("%Y-%m-%d"),
                    "present": present_count,
                    "absent": absent_count
                })

            return {
                "daily_attendance": daily_attendance
            }

        except Exception as e:
            logger.error(f"Error getting attendance metrics: {str(e)}")
            return {"daily_attendance": []}

    async def _get_shipment_metrics(self) -> Dict[str, Any]:
        """Get shipment-related metrics"""
        try:
            # Total shipments
            total_result = await self.session.execute(
                select(func.count(Shipment.id))
                .where(Shipment.is_deleted == False)
            )
            total_shipments = total_result.scalar()

            # Status breakdown
            status_breakdown = []
            for status in ShipmentStatus:
                count_result = await self.session.execute(
                    select(func.count(Shipment.id))
                    .where(
                        and_(
                            Shipment.status == status,
                            Shipment.is_deleted == False
                        )
                    )
                )
                count = count_result.scalar()
                
                status_breakdown.append({
                    "status": status.value,
                    "count": count,
                    "color": self._get_status_color(status.value)
                })

            # Recent shipment products
            shipment_products_result = await self.session.execute(
                select(Shipment)
                .where(Shipment.is_deleted == False)
                .order_by(desc(Shipment.created_at))
                .limit(5)
            )

            shipment_products = []
            for shipment in shipment_products_result.scalars():
                shipment_products.append({
                    "shipment_number": shipment.shipment_number,
                    "status": shipment.status.value
                })

            return {
                "total_shipments": total_shipments,
                "status_breakdown": status_breakdown,
                "shipment_products": shipment_products
            }

        except Exception as e:
            logger.error(f"Error getting shipment metrics: {str(e)}")
            return {"total_shipments": 0, "status_breakdown": [], "shipment_products": []}

    async def _get_reorder_metrics(self) -> Dict[str, Any]:
        """Get reorder request metrics"""
        try:
            # Status counts
            pending_result = await self.session.execute(
                select(func.count(ReorderRequest.id))
                .where(
                    and_(
                        ReorderRequest.status == ReorderRequestStatus.PENDING,
                        ReorderRequest.is_active == True
                    )
                )
            )
            pending_requests = pending_result.scalar()

            approved_result = await self.session.execute(
                select(func.count(ReorderRequest.id))
                .where(
                    and_(
                        ReorderRequest.status == ReorderRequestStatus.APPROVED,
                        ReorderRequest.is_active == True
                    )
                )
            )
            approved_requests = approved_result.scalar()

            rejected_result = await self.session.execute(
                select(func.count(ReorderRequest.id))
                .where(
                    and_(
                        ReorderRequest.status == ReorderRequestStatus.REJECTED,
                        ReorderRequest.is_active == True
                    )
                )
            )
            rejected_requests = rejected_result.scalar()

            # Recent requests
            recent_result = await self.session.execute(
                select(ReorderRequest)
                .where(ReorderRequest.is_active == True)
                .order_by(desc(ReorderRequest.created_at))
                .limit(5)
            )

            recent_requests = []
            for request in recent_result.scalars():
                recent_requests.append({
                    "request_number": request.request_number,
                    "status": request.status.value,
                    "estimated_cost": float(request.total_estimated_cost or 0)
                })

            return {
                "pending_requests": pending_requests,
                "approved_requests": approved_requests,
                "rejected_requests": rejected_requests,
                "recent_requests": recent_requests
            }

        except Exception as e:
            logger.error(f"Error getting reorder metrics: {str(e)}")
            return {"pending_requests": 0, "approved_requests": 0, "rejected_requests": 0, "recent_requests": []}

    async def _get_holiday_info(self, today: date) -> Dict[str, Any]:
        """Get holiday information"""
        try:
            # Today's holiday
            today_holiday_result = await self.session.execute(
                select(Holiday)
                .where(
                    and_(
                        Holiday.date == today,
                        Holiday.is_active == True
                    )
                )
            )
            today_holiday = today_holiday_result.scalar_one_or_none()

            # Upcoming holidays
            upcoming_result = await self.session.execute(
                select(Holiday)
                .where(
                    and_(
                        Holiday.date >= today,
                        Holiday.is_active == True
                    )
                )
                .order_by(Holiday.date)
                .limit(6)
            )

            upcoming_holidays = []
            for holiday in upcoming_result.scalars():
                upcoming_holidays.append({
                    "name": holiday.name,
                    "date": holiday.date.strftime("%d-%m-%Y"),
                    "description": holiday.description
                })

            return {
                "today_holiday": {
                    "name": today_holiday.name,
                    "description": today_holiday.description
                } if today_holiday else None,
                "upcoming_holidays": upcoming_holidays
            }

        except Exception as e:
            logger.error(f"Error getting holiday info: {str(e)}")
            return {"today_holiday": None, "upcoming_holidays": []}

    def _get_status_color(self, status: str) -> str:
        """Get color for status visualization"""
        color_map = {
            "IN_TRANSIT": "#fbbf24",
            "DELIVERED": "#10b981", 
            "READY_FOR_PICKUP": "#06b6d4",
            "PICKED_UP": "#8b5cf6",
            "OUT_FOR_DELIVERY": "#f59e0b",
            "CANCELLED": "#ef4444"
        }
        return color_map.get(status, "#6b7280")
    
    async def _get_po_approvals(self) -> List[Dict[str, Any]]:
        """Get PO approvals with user details"""
        try:
            # Get pending POs with user details
            po_approvals_result = await self.session.execute(
                select(PurchaseOrder, Employee)
                .outerjoin(Employee, Employee.id == PurchaseOrder.requested_by)
                .where(
                    and_(
                        PurchaseOrder.status == PurchaseOrderStatus.PENDING,
                        PurchaseOrder.is_deleted == False
                    )
                )
                .order_by(desc(PurchaseOrder.created_at))
                .limit(5)
            )

            po_approvals = []
            for po, employee in po_approvals_result:
                po_approvals.append({
                    "po_number": po.po_number,
                    "requested_by": f"{employee.first_name} {employee.last_name}" if employee else "Unknown",
                    "status": po.status.value,
                    "amount": float(po.total_amount),
                    "order_date": po.order_date.strftime("%Y-%m-%d")
                })

            return po_approvals

        except Exception as e:
            logger.error(f"Error getting PO approvals: {str(e)}")
            return []

    async def get_yearly_salary_report(self) -> Dict[str, Any]:
        """Get yearly salary report with 12 months breakdown"""
        try:
                       
            year = date.today().year

            # Get total paid salary for the year
            total_paid_result = await self.session.execute(
                select(func.coalesce(func.sum(Salary.net_salary), 0))
                .where(
                    and_(
                        extract('year', Salary.salary_month) == year,
                        Salary.payment_status == SalaryPaymentStatus.PAID
                    )
                )
            )
            total_paid_salary = float(total_paid_result.scalar())

            # Get monthly breakdown for all 12 months
            monthly_breakdown = []
            for month in range(1, 13):
                month_result = await self.session.execute(
                    select(func.coalesce(func.sum(Salary.net_salary), 0))
                    .where(
                        and_(
                            extract('year', Salary.salary_month) == year,
                            extract('month', Salary.salary_month) == month,
                            Salary.payment_status == SalaryPaymentStatus.PAID
                        )
                    )
                )
                month_total = float(month_result.scalar())
                
                month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                
                monthly_breakdown.append({
                    "month": month_names[month - 1],
                    "month_number": month,
                    "net_salary": month_total,
                    "year": year
                })

            return {
                "year": year,
                "total_paid_salary": total_paid_salary,
                "monthly_breakdown": monthly_breakdown
            }

        except Exception as e:
            logger.error(f"Error getting yearly salary report: {str(e)}")
            return {
                "year": year or date.today().year,
                "total_paid_salary": 0,
                "monthly_breakdown": []
            }