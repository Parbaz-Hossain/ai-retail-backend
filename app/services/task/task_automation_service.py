from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
from app.models.task.task import Task
from app.models.task.task_type import TaskType
from app.models.shared.enums import TaskStatus, TaskPriority, ReferenceType
from app.services.task.task_service import TaskService
from app.schemas.task.task_schema import TaskCreate

class TaskAutomationService:
    """Service for creating automated tasks based on system events"""
    
    def __init__(self, db: AsyncSession, task_service: TaskService):
        self.db = db
        self.task_service = task_service


    async def create_low_stock_alert_task(self, item_id: int, location_id: int, current_stock: float, reorder_point: float, user_id: int):
        """Create task for low stock alert with notifications"""
        
        # Get low stock alert task type
        result = await self.db.execute(
            select(TaskType).where(
                and_(
                    TaskType.name == "Low Stock Alert",
                    TaskType.category == "INVENTORY"
                )
            )
        )
        task_type = result.scalar_one_or_none()
        
        if not task_type:
            return None
        
        # Check if similar task already exists
        existing_result = await self.db.execute(
            select(Task).where(
                and_(
                    Task.reference_type == ReferenceType.LOW_STOCK_ALERT.value,
                    Task.reference_id == item_id,
                    Task.location_id == location_id,
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                    Task.is_active == True
                )
            )
        )
        existing_task = existing_result.scalar_one_or_none()
        
        if existing_task:
            return existing_task
        
        # Get item and location details for task creation
        from app.models.inventory.item import Item
        from app.models.organization.location import Location
        
        item_result = await self.db.execute(
            select(Item).where(Item.id == item_id)
        )
        item = item_result.scalar_one_or_none()
        
        location_result = await self.db.execute(
            select(Location).where(Location.id == location_id)
        )
        location = location_result.scalar_one_or_none()
        
        if not item or not location:
            return None
        
        # Determine priority based on how critical the stock level is
        stock_percentage = (current_stock / reorder_point) * 100 if reorder_point > 0 else 0
        
        if stock_percentage <= 25:  # Less than 25% of reorder point
            priority = TaskPriority.URGENT
        elif stock_percentage <= 50:  # Less than 50% of reorder point
            priority = TaskPriority.HIGH
        else:
            priority = TaskPriority.MEDIUM
        
        # Create new task
        task_data = TaskCreate(
            title=f"Low Stock Alert - {item.name} at {location.name}",
            description=f"Item '{item.name}' at location '{location.name}' has fallen below reorder point. Current stock: {current_stock}, Reorder point: {reorder_point}. Immediate restocking required.",
            task_type_id=task_type.id,
            reference_type=ReferenceType.LOW_STOCK_ALERT.value,
            reference_id=item_id,
            reference_data={
                "current_stock": current_stock,
                "reorder_point": reorder_point,
                "item_id": item_id,
                "item_name": item.name,
                "location_id": location_id,
                "location_name": location.name,
                "stock_percentage": round(stock_percentage, 2)
            },
            location_id=location_id,
            priority=priority,
            due_date=datetime.utcnow() + timedelta(hours=24 if priority == TaskPriority.URGENT else 48)
        )
        
        task = await self.task_service.create_task(task_data, created_by=user_id or 1)
        
        return task
   
    async def create_purchase_approval_task(self, po_id: int, total_amount: float, user_id: int):
        """Create task for purchase order approval"""
        
        result = await self.db.execute(
            select(TaskType).where(
                and_(
                    TaskType.name == "Purchase Order Approval",
                    TaskType.category == "PURCHASE"
                )
            )
        )
        task_type = result.scalar_one_or_none()
        
        if not task_type:
            return None
        
        # Determine priority based on amount
        priority = TaskPriority.HIGH if total_amount > 10000 else TaskPriority.MEDIUM
        
        task_data = TaskCreate(
            title=f"Approve Purchase Order - PO#{po_id}",
            description=f"Review and approve purchase order #{po_id} with total amount ${total_amount}",
            task_type_id=task_type.id,
            reference_type=ReferenceType.PURCHASE_ORDER.value,
            reference_id=po_id,
            reference_data={
                "po_id": po_id,
                "total_amount": total_amount
            },
            priority=priority,
            due_date=datetime.utcnow() + timedelta(days=2)
        )
        
        return await self.task_service.create_task(task_data, created_by=user_id or 1)

    async def create_shipment_delivery_task(self, shipment_id: int, driver_id: int, user_id: int):
        """Create task for shipment delivery"""
        
        result = await self.db.execute(
            select(TaskType).where(
                and_(
                    TaskType.name == "Shipment Delivery",
                    TaskType.category == "LOGISTICS"
                )
            )
        )
        task_type = result.scalar_one_or_none()
        
        if not task_type:
            return None
        
        task_data = TaskCreate(
            title=f"Deliver Shipment - #{shipment_id}",
            description=f"Complete delivery of shipment #{shipment_id}",
            task_type_id=task_type.id,
            reference_type=ReferenceType.SHIPMENT_DELIVERY.value,
            reference_id=shipment_id,
            reference_data={
                "shipment_id": shipment_id,
                "driver_id": driver_id
            },
            assigned_to=driver_id,
            priority=TaskPriority.HIGH,
            due_date=datetime.utcnow() + timedelta(days=1)
        )
        
        return await self.task_service.create_task(task_data, created_by=user_id)

    async def create_salary_generation_task(self, employee_id: int, salary_month: str, user_id: int):
        """Create task for salary generation"""
        
        result = await self.db.execute(
            select(TaskType).where(
                and_(
                    TaskType.name == "Salary Generation",
                    TaskType.category == "HR"
                )
            )
        )
        task_type = result.scalar_one_or_none()
        
        if not task_type:
            return None
        
        task_data = TaskCreate(
            title=f"Generate Salary - Employee #{employee_id} - {salary_month}",
            description=f"Generate and process salary for employee #{employee_id} for {salary_month}",
            task_type_id=task_type.id,
            reference_type=ReferenceType.SALARY_GENERATION.value,
            reference_id=employee_id,
            reference_data={
                "employee_id": employee_id,
                "salary_month": salary_month
            },
            priority=TaskPriority.MEDIUM,
            due_date=datetime.utcnow() + timedelta(days=3)
        )
        
        return await self.task_service.create_task(task_data, created_by=user_id or 1)
    
    async def create_equipment_maintenance_task(self, equipment_type: str, location_id: int):
        """Create recurring equipment maintenance task"""
        
        result = await self.db.execute(
            select(TaskType).where(
                and_(
                    TaskType.name == "Equipment Maintenance",
                    TaskType.category == "MAINTENANCE"
                )
            )
        )
        task_type = result.scalar_one_or_none()
        
        if not task_type:
            return None
        
        task_data = TaskCreate(
            title=f"{equipment_type} Maintenance",
            description=f"Perform scheduled maintenance on {equipment_type}",
            task_type_id=task_type.id,
            reference_type=ReferenceType.EQUIPMENT_MAINTENANCE.value,
            reference_data={
                "equipment_type": equipment_type,
                "maintenance_type": "SCHEDULED"
            },
            location_id=location_id,
            priority=TaskPriority.MEDIUM,
            is_recurring=True,
            recurrence_pattern="MONTHLY",
            due_date=datetime.utcnow() + timedelta(days=30)
        )
        
        return await self.task_service.create_task(task_data, created_by=1)