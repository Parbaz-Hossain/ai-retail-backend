"""
Integration service to connect task management with existing operations
"""
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.services.task.task_automation_service import TaskAutomationService
from app.services.task.task_service import TaskService
from app.models.inventory.stock_level import StockLevel
from app.models.inventory.item import Item
from app.models.inventory.reorder_request import ReorderRequest
from app.models.hr.employee import Employee
from app.models.hr.salary import Salary
from app.models.purchase.purchase_order import PurchaseOrder
from app.models.logistics.shipment import Shipment

class TaskIntegrationService:
    """Service to integrate task management with existing operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_service = TaskService(db)
        self.automation_service = TaskAutomationService(db, self.task_service)

    async def check_and_create_low_stock_tasks(self, user_id: int):
        """Check stock levels and create low stock alert tasks"""
        # Get items below reorder point
        result = await self.db.execute(
            select(StockLevel)
            .options(selectinload(StockLevel.item))
            .join(Item).where(
                and_(
                    StockLevel.current_stock <= Item.reorder_point,
                    Item.is_active == True,
                    StockLevel.current_stock > 0
                )
            )
        )
        low_stock_items = result.scalars().all()
        
        for stock_level in low_stock_items:
            await self.automation_service.create_low_stock_alert_task(
                item_id=stock_level.item_id,
                location_id=stock_level.location_id,
                current_stock=float(stock_level.current_stock),
                reorder_point=float(stock_level.item.reorder_point),
                user_id=user_id
            )

    async def create_reorder_approval_task(self, reorder_request: ReorderRequest):
        """Create task for reorder request approval"""
        from app.schemas.task.task_schema import TaskCreate
        from app.models.shared.enums import TaskPriority, ReferenceType
        from datetime import datetime, timedelta
        
        # Get or create task type
        task_type = await self._get_or_create_task_type(
            name="Reorder Request Approval",
            category="INVENTORY",
            description="Review and approve reorder requests"
        )
        
        task_data = TaskCreate(
            title=f"Approve Reorder Request - {reorder_request.request_number}",
            description=f"Review and approve reorder request for location: {reorder_request.location.name}",
            task_type_id=task_type.id,
            reference_type=ReferenceType.REORDER_REQUEST.value,
            reference_id=reorder_request.id,
            reference_data={
                "request_number": reorder_request.request_number,
                "location_id": reorder_request.location_id,
                "total_estimated_cost": float(reorder_request.total_estimated_cost or 0)
            },
            location_id=reorder_request.location_id,
            priority=TaskPriority.MEDIUM,
            due_date=datetime.utcnow() + timedelta(days=2)
        )
        
        return await self.task_service.create_task(task_data, created_by=reorder_request.requested_by or 1)

    async def create_purchase_approval_task(self, purchase_order: PurchaseOrder, user_id: int):
        """Create task for purchase order approval"""
        return await self.automation_service.create_purchase_approval_task(
            po_id=purchase_order.id,
            total_amount=float(purchase_order.total_amount),
            user_id=user_id
        )

    async def create_shipment_tasks(self, shipment: Shipment, user_id: int):
        """Create tasks related to shipment"""      
        
        # Create tracking/monitoring task for logistics manager
        from app.schemas.task.task_schema import TaskCreate
        from app.models.shared.enums import TaskPriority, ReferenceType
        from datetime import datetime, timedelta

        # Create delivery task for driver
        if shipment.driver_id:
            await self.automation_service.create_shipment_delivery_task(
                shipment_id=shipment.id,
                driver_id=shipment.driver_id,
                user_id=user_id or shipment.created_by or 1
            )
        
        task_type = await self._get_or_create_task_type(
            name="Shipment Monitoring",
            category="LOGISTICS",
            description="Monitor shipment progress and ensure timely delivery"
        )
        
        task_data = TaskCreate(
            title=f"Monitor Shipment - {shipment.shipment_number}",
            description=f"Track and monitor shipment {shipment.shipment_number} delivery progress",
            task_type_id=task_type.id,
            reference_type=ReferenceType.SHIPMENT_DELIVERY.value,
            reference_id=shipment.id,
            reference_data={
                "shipment_number": shipment.shipment_number,
                "from_location_id": shipment.from_location_id,
                "to_location_id": shipment.to_location_id
            },
            priority=TaskPriority.MEDIUM,
            due_date=shipment.expected_delivery_date
        )
        
        return await self.task_service.create_task(task_data, created_by=user_id or shipment.created_by or 1)

    async def create_salary_processing_tasks(self, user_id: int):
        """Create monthly salary processing tasks"""
        from datetime import datetime
        from calendar import monthrange
        
        # Only create if we're past 25th of the month
        current_date = datetime.now()
        if current_date.day < 25:
            return
        
        # Get active employees
        result = await self.db.execute(
            select(Employee).where(Employee.is_active == True)
        )
        active_employees = result.scalars().all()
        
         # Create salary generation tasks for each employee
        for employee in active_employees:
            salary_month_str = f"{current_date.year}-{current_date.month:02d}"
        
        # Create a proper date object for comparison
        salary_month_date = date(current_date.year, current_date.month, 1)
        
        # Check if salary already processed this month
        salary_result = await self.db.execute(
            select(Salary).where(
                and_(
                    Salary.employee_id == employee.id,
                    Salary.salary_month == salary_month_date  # Use date object instead of string
                )
            )
        )
        existing_salary = salary_result.scalar_one_or_none()
        
        if not existing_salary:
            await self.automation_service.create_salary_generation_task(
                employee_id=employee.id,
                salary_month=salary_month_str,
                user_id=user_id
            )
    
    async def create_maintenance_tasks(self, location_id: int):
        """Create recurring maintenance tasks"""
        maintenance_types = [
            "Coffee Machine Maintenance",
            "Kitchen Equipment Check",
            "POS System Update",
            "Inventory Count",
            "Safety Equipment Inspection"
        ]
        
        for maintenance_type in maintenance_types:
            await self.automation_service.create_equipment_maintenance_task(
                equipment_type=maintenance_type,
                location_id=location_id
            )

    async def _get_or_create_task_type(self, name: str, category: str, description: str):
        """Get existing task type or create new one"""
        from app.models.task.task_type import TaskType
        
        result = await self.db.execute(
            select(TaskType).where(
                and_(
                    TaskType.name == name,
                    TaskType.category == category
                )
            )
        )
        task_type = result.scalar_one_or_none()
        
        if not task_type:
            task_type = TaskType(
                name=name,
                category=category,
                description=description,
                auto_assign_enabled=False,
                default_priority="MEDIUM",
                sla_hours=48,
                requires_approval=False
            )
            self.db.add(task_type)
            await self.db.commit()
            await self.db.refresh(task_type)
        
        return task_type