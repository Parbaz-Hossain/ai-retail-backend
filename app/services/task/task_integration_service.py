"""
Integration service to connect task management with existing operations
"""
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.models.shared.enums import ReferenceType, TaskPriority
from app.models.task.task_type import TaskType
from app.schemas.task.task_schema import TaskCreate
from app.services.communication.email_service import EmailService
from app.services.task.task_automation_service import TaskAutomationService
from app.services.task.task_service import TaskService
from app.models.inventory.stock_level import StockLevel
from app.models.inventory.item import Item
from app.models.inventory.reorder_request import ReorderRequest
from app.models.hr.employee import Employee
from app.models.hr.salary import Salary
from app.models.purchase.purchase_order import PurchaseOrder
from app.models.logistics.shipment import Shipment
from app.services.notification.notification_service import NotificationService
from app.services.auth.user_service import UserService

class TaskIntegrationService:
    """Service to integrate task management with existing operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_service = TaskService(db)
        self.automation_service = TaskAutomationService(db, self.task_service)
        self.user_service = UserService(db)

    async def check_and_create_low_stock_tasks(self, user_id: int):
        """Check stock levels and create low stock alert tasks with notifications"""
        # Get items below reorder point
        result = await self.db.execute(
            select(StockLevel)
            .options(
                selectinload(StockLevel.item),
                selectinload(StockLevel.location)
            )
            .join(Item).where(
                and_(
                    StockLevel.current_stock <= Item.reorder_point,
                    Item.is_active == True,
                    StockLevel.current_stock > 0,
                    Item.reorder_point > 0
                )
            )
        )
        low_stock_items = result.scalars().all()

        if not low_stock_items:
            return

        # Send notifications and create tasks
        email_service = EmailService()
        notification_service = NotificationService(self.db)
        
        # Get inventory managers and branch managers
        notification_users = await self.user_service.get_users_by_roles(["INVENTORY_MANAGER", "BRANCH_MANAGER"])
        
        created_tasks = []
        
        for stock_level in low_stock_items:
            # Create the low stock alert task
            task = await self.automation_service.create_low_stock_alert_task(
                item_id=stock_level.item_id,
                location_id=stock_level.location_id,
                current_stock=float(stock_level.current_stock),
                reorder_point=float(stock_level.item.reorder_point),
                user_id=user_id
            )
            
            if task:
                created_tasks.append({
                    'task': task,
                    'item': stock_level.item,
                    'location': stock_level.location,
                    'current_stock': stock_level.current_stock,
                    'reorder_point': stock_level.item.reorder_point
                })

        if created_tasks and notification_users:
            # Group tasks by location for better email organization
            tasks_by_location = {}
            for task_data in created_tasks:
                location_name = task_data['location'].name
                if location_name not in tasks_by_location:
                    tasks_by_location[location_name] = []
                tasks_by_location[location_name].append(task_data)

            # Send notifications to inventory managers
            for user in notification_users:
                # Create summary for email
                total_low_stock_items = len(created_tasks)
                
                # Build email content
                location_summaries = []
                for location_name, location_tasks in tasks_by_location.items():
                    item_list = []
                    for task_data in location_tasks:
                        item_list.append(f"- {task_data['item'].name}: {task_data['current_stock']} (reorder at {task_data['reorder_point']})")
                    
                    location_summaries.append(f"""
                    <h4>{location_name} ({len(location_tasks)} items)</h4>
                    <ul>
                        {'<li>' + '</li><li>'.join([td['item'].name + f": {td['current_stock']} units (reorder at {td['reorder_point']})" for td in location_tasks]) + '</li>'}
                    </ul>
                    """)

                # Send email notification
                await email_service.send_email(
                    to_email=user.email,
                    subject=f"🚨 Low Stock Alert - {total_low_stock_items} Items Need Attention",
                    html_content=f"""
                    <h2>Low Stock Alert - Immediate Action Required</h2>
                    <p>The following {total_low_stock_items} items have fallen below their reorder points:</p>
                    
                    {''.join(location_summaries)}
                    
                    <p><strong>Action Required:</strong></p>
                    <ul>
                        <li>Review current stock levels</li>
                        <li>Create reorder requests for critical items</li>
                        <li>Check for any pending purchase orders</li>
                        <li>Consider emergency transfers from other locations</li>
                    </ul>
                    
                    <p>Please check your task dashboard for detailed tasks and take appropriate action.</p>
                    """,
                    text_content=f"LOW STOCK ALERT: {total_low_stock_items} items need reordering. Check your dashboard for details."
                )
                
                # Send real-time UI notification for summary
                await notification_service.send_real_time_notification(
                    user_id=user.id,
                    notification_type="LOW_STOCK_ALERT",
                    title="🚨 Low Stock Alert",
                    message=f"{total_low_stock_items} items are below reorder point and need immediate attention",
                    data={
                        "total_items": total_low_stock_items,
                        "locations_affected": len(tasks_by_location),
                        "task_ids": [task_data['task'].id for task_data in created_tasks],
                        "priority": "HIGH"
                    }
                )
                
                # Send individual notifications for high-priority items
                for task_data in created_tasks:
                    if task_data['current_stock'] <= (task_data['reorder_point'] * 0.5):  # Less than 50% of reorder point
                        await notification_service.send_real_time_notification(
                            user_id=user.id,
                            notification_type="CRITICAL_LOW_STOCK",
                            title="🔴 Critical Low Stock",
                            message=f"{task_data['item'].name} at {task_data['location'].name}: Only {task_data['current_stock']} units left!",
                            data={
                                "task_id": task_data['task'].id,
                                "item_id": task_data['item'].id,
                                "item_name": task_data['item'].name,
                                "location_id": task_data['location'].id,
                                "location_name": task_data['location'].name,
                                "current_stock": float(task_data['current_stock']),
                                "reorder_point": float(task_data['reorder_point']),
                                "priority": "CRITICAL"
                            }
                        )

    async def create_reorder_approval_task(self, reorder_request: ReorderRequest):
        """Create task for reorder request approval"""
        
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
        
        task = await self.task_service.create_task(task_data, created_by=reorder_request.requested_by or 1)

        # region Send detailed HTML email to each approver
        if task:
            # Send notifications
            
            email_service = EmailService()
            notification_service = NotificationService(self.db)
            
            # Find users with INVENTORY_MANAGER or BRANCH_MANAGER roles
            approval_users = await self.user_service.get_users_by_roles(["INVENTORY_MANAGER", "BRANCH_MANAGER"])
            
            # Create the approval link
            approval_link = f"https://bluemen-cafe-management-ai.vercel.app/dashboard/stock-operation/recorder-request/"
            
            for user in approval_users:
                # Send email notification
                await email_service.send_email(
                    to_email=user.email,
                    subject=f"Reorder Request Approval Required - {reorder_request.request_number}",
                    html_content=f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    </head>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                        
                        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                            <h2 style="color: #2c3e50; margin-top: 0;">Reorder Request Approval Required</h2>
                            <p style="margin-bottom: 0; color: #666;">A new reorder request requires your immediate attention and approval.</p>
                        </div>
                        
                        <div style="background-color: #ffffff; border: 1px solid #e9ecef; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                            <h3 style="color: #495057; margin-top: 0; border-bottom: 2px solid #e9ecef; padding-bottom: 10px;">Reorder Details</h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold; width: 30%;">Request Number:</td>
                                    <td style="padding: 8px 0;">{reorder_request.request_number}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Location:</td>
                                    <td style="padding: 8px 0;">{reorder_request.location.name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Total Estimated Cost:</td>
                                    <td style="padding: 8px 0; color: #fd7e14; font-weight: bold; font-size: 16px;">${reorder_request.total_estimated_cost or 0}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Priority:</td>
                                    <td style="padding: 8px 0;">{reorder_request.priority}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Required Date:</td>
                                    <td style="padding: 8px 0;">{reorder_request.required_date.strftime('%B %d, %Y') if hasattr(reorder_request.required_date, 'strftime') else reorder_request.required_date}</td>
                                </tr>
                            </table>
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{approval_link}" 
                            style="background-color: #fd7e14; 
                                    color: white; 
                                    padding: 15px 30px; 
                                    text-decoration: none; 
                                    border-radius: 5px; 
                                    font-weight: bold; 
                                    font-size: 16px;
                                    display: inline-block;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                    transition: background-color 0.3s;">
                                📦 Review & Approve Reorder
                            </a>
                        </div>
                        
                        <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 15px; margin: 20px 0;">
                            <p style="margin: 0; color: #856404;">
                                <strong>⚠️ Action Required:</strong> Please review this reorder request as soon as possible. 
                                Click the button above to access your dashboard and approve or reject this reorder.
                            </p>
                        </div>
                        
                        <hr style="border: none; border-top: 1px solid #e9ecef; margin: 25px 0;">
                        
                        <div style="color: #6c757d; font-size: 14px;">
                            <p><strong>Alternative Access:</strong></p>
                            <p>If the button doesn't work, copy and paste this link into your browser:</p>
                            <p style="background-color: #f8f9fa; padding: 10px; border-radius: 4px; word-break: break-all;">
                                {approval_link}
                            </p>
                            
                            <p style="margin-top: 20px;">
                                <strong>Need Help?</strong> Contact the system administrator if you experience any issues accessing the approval dashboard.
                            </p>
                        </div>
                        
                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e9ecef; text-align: center; color: #6c757d; font-size: 12px;">
                            <p>This is an automated message from Bluemen Cafe Management System.</p>
                            <p>Please do not reply to this email.</p>
                        </div>
                        
                    </body>
                    </html>
                    """,
                    text_content=f"""
                    Reorder Request Approval Required
                    
                    A new reorder request requires your approval:
                    
                    Request Number: {reorder_request.request_number}
                    Location: {reorder_request.location.name}
                    Total Estimated Cost: ${reorder_request.total_estimated_cost or 0}
                    Priority: {reorder_request.priority}
                    Required Date: {reorder_request.required_date.strftime('%B %d, %Y') if hasattr(reorder_request.required_date, 'strftime') else reorder_request.required_date}
                    
                    To approve this reorder, please visit:
                    {approval_link}
                    
                    Please review and approve this reorder request in your task dashboard as soon as possible.
                    
                    ---
                    This is an automated message from Bluemen Cafe Management System.
                    """
                )
                
                # Send real-time UI notification
                await notification_service.send_real_time_notification(
                    user_id=user.id,
                    notification_type="TASK_ASSIGNED",
                    title="New Reorder Approval Task",
                    message=f"Reorder Request {reorder_request.request_number} requires your approval",
                    data={
                        "task_id": task.id,
                        "reorder_request_id": reorder_request.id,
                        "estimated_cost": float(reorder_request.total_estimated_cost or 0)
                    }
                )
        
        return task
        # endregion

    async def create_purchase_approval_task(self, purchase_order: PurchaseOrder, user_id: int):
        """Create task for purchase order approval"""

        task = await self.automation_service.create_purchase_approval_task(
            po_id=purchase_order.id,
            total_amount=float(purchase_order.total_amount),
            user_id=user_id
        )

        # region Send detailed HTML email to each approver
        if task:
            # Send email notification
            
            email_service = EmailService()
            ui_notification_service = NotificationService(self.db)
            
            # Find users with BRANCH_MANAGER or PURCHASE_MANAGER roles
            approval_users = await self.user_service.get_users_by_roles(["BRANCH_MANAGER", "PURCHASE_MANAGER"])
            
            # Create the approval link (you might want to include task_id or po_id as parameter)
            approval_link = f"https://bluemen-cafe-management-ai.vercel.app/dashboard/purchase-management/purchase-order/"
            
            for user in approval_users:
                # Send email notification
                await email_service.send_email(
                    to_email=user.email,
                    subject=f"Purchase Order Approval Required - {purchase_order.po_number}",
                    html_content=f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    </head>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                        
                        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                            <h2 style="color: #2c3e50; margin-top: 0;">Purchase Order Approval Required</h2>
                            <p style="margin-bottom: 0; color: #666;">A new purchase order requires your immediate attention and approval.</p>
                        </div>
                        
                        <div style="background-color: #ffffff; border: 1px solid #e9ecef; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                            <h3 style="color: #495057; margin-top: 0; border-bottom: 2px solid #e9ecef; padding-bottom: 10px;">Order Details</h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold; width: 30%;">PO Number:</td>
                                    <td style="padding: 8px 0;">{purchase_order.po_number}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Supplier:</td>
                                    <td style="padding: 8px 0;">{purchase_order.supplier.name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Total Amount:</td>
                                    <td style="padding: 8px 0; color: #dc3545; font-weight: bold; font-size: 16px;">${purchase_order.total_amount:,.2f}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Order Date:</td>
                                    <td style="padding: 8px 0;">{purchase_order.order_date.strftime('%B %d, %Y')}</td>
                                </tr>
                            </table>
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{approval_link}" 
                            style="background-color: #28a745; 
                                    color: white; 
                                    padding: 15px 30px; 
                                    text-decoration: none; 
                                    border-radius: 5px; 
                                    font-weight: bold; 
                                    font-size: 16px;
                                    display: inline-block;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                    transition: background-color 0.3s;">
                                📋 Review & Approve Order
                            </a>
                        </div>
                        
                        <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 15px; margin: 20px 0;">
                            <p style="margin: 0; color: #856404;">
                                <strong>⚠️ Action Required:</strong> Please review this purchase order as soon as possible. 
                                Click the button above to access your dashboard and approve or reject this order.
                            </p>
                        </div>
                        
                        <hr style="border: none; border-top: 1px solid #e9ecef; margin: 25px 0;">
                        
                        <div style="color: #6c757d; font-size: 14px;">
                            <p><strong>Alternative Access:</strong></p>
                            <p>If the button doesn't work, copy and paste this link into your browser:</p>
                            <p style="background-color: #f8f9fa; padding: 10px; border-radius: 4px; word-break: break-all;">
                                {approval_link}
                            </p>
                            
                            <p style="margin-top: 20px;">
                                <strong>Need Help?</strong> Contact the system administrator if you experience any issues accessing the approval dashboard.
                            </p>
                        </div>
                        
                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e9ecef; text-align: center; color: #6c757d; font-size: 12px;">
                            <p>This is an automated message from Bluemen Cafe Management System.</p>
                            <p>Please do not reply to this email.</p>
                        </div>
                        
                    </body>
                    </html>
                    """,
                    text_content=f"""
                    Purchase Order Approval Required
                    
                    A new purchase order requires your approval:
                    
                    PO Number: {purchase_order.po_number}
                    Supplier: {purchase_order.supplier.name}
                    Total Amount: ${purchase_order.total_amount:,.2f}
                    Order Date: {purchase_order.order_date.strftime('%B %d, %Y')}
                    
                    To approve this order, please visit:
                    {approval_link}
                    
                    Please review and approve this purchase order in your task dashboard as soon as possible.
                    
                    ---
                    This is an automated message from Bluemen Cafe Management System.
                    """
                )
                
                # Send real-time UI notification
                await ui_notification_service.send_real_time_notification(
                    user_id=user.id,
                    notification_type="TASK_ASSIGNED",
                    title="New Purchase Approval Task",
                    message=f"Purchase Order {purchase_order.po_number} requires your approval",
                    data={
                        "task_id": task.id,
                        "po_id": purchase_order.id,
                        "amount": float(purchase_order.total_amount)
                    }
                )        

            return task
        # endregion
    
    async def create_transfer_approval_task(self, transfer, user_id: int):
        """Create task for transfer approval with notifications"""
        
        # Get or create task type
        task_type = await self._get_or_create_task_type(
            name="Transfer Request Approval",
            category="INVENTORY",
            description="Review and approve transfer requests"
        )
        
        task_data = TaskCreate(
            title=f"Approve Transfer Request - {transfer.transfer_number}",
            description=f"Review and approve transfer from {transfer.from_location.name} to {transfer.to_location.name}",
            task_type_id=task_type.id,
            reference_type=ReferenceType.TRANSFER_REQUEST.value,
            reference_id=transfer.id,
            reference_data={
                "transfer_number": transfer.transfer_number,
                "from_location_id": transfer.from_location_id,
                "to_location_id": transfer.to_location_id,
                "item_count": len(transfer.items)
            },
            location_id=transfer.from_location_id,
            priority=TaskPriority.MEDIUM,
            due_date=datetime.utcnow() + timedelta(days=1)
        )
        
        task = await self.task_service.create_task(task_data, created_by=user_id)
        
        # region Send detailed HTML email to each approver
        if task:
            # Send notifications
            
            email_service = EmailService()
            notification_service = NotificationService(self.db)
            
            # Find users with INVENTORY_MANAGER or BRANCH_MANAGER roles
            approval_users = await self.user_service.get_users_by_roles(["INVENTORY_MANAGER", "BRANCH_MANAGER"])
            
            # Create the approval link
            approval_link = f"https://bluemen-cafe-management-ai.vercel.app/dashboard/stock-operation/stock-transfer/{transfer.id}?task_id={task.id}"
            
            for user in approval_users:
                # Send email notification
                await email_service.send_email(
                    to_email=user.email,
                    subject=f"Transfer Request Approval Required - {transfer.transfer_number}",
                    html_content=f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    </head>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                        
                        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                            <h2 style="color: #2c3e50; margin-top: 0;">Transfer Request Approval Required</h2>
                            <p style="margin-bottom: 0; color: #666;">A new transfer request requires your immediate attention and approval.</p>
                        </div>
                        
                        <div style="background-color: #ffffff; border: 1px solid #e9ecef; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                            <h3 style="color: #495057; margin-top: 0; border-bottom: 2px solid #e9ecef; padding-bottom: 10px;">Transfer Details</h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold; width: 30%;">Transfer Number:</td>
                                    <td style="padding: 8px 0;">{transfer.transfer_number}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">From Location:</td>
                                    <td style="padding: 8px 0;">{transfer.from_location.name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">To Location:</td>
                                    <td style="padding: 8px 0;">{transfer.to_location.name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Transfer Date:</td>
                                    <td style="padding: 8px 0;">{transfer.transfer_date.strftime('%B %d, %Y') if hasattr(transfer.transfer_date, 'strftime') else transfer.transfer_date}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; font-weight: bold;">Items Count:</td>
                                    <td style="padding: 8px 0; color: #007bff; font-weight: bold; font-size: 16px;">{len(transfer.items)} items</td>
                                </tr>
                            </table>
                        </div>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{approval_link}" 
                            style="background-color: #007bff; 
                                    color: white; 
                                    padding: 15px 30px; 
                                    text-decoration: none; 
                                    border-radius: 5px; 
                                    font-weight: bold; 
                                    font-size: 16px;
                                    display: inline-block;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                    transition: background-color 0.3s;">
                                🔄 Review & Approve Transfer
                            </a>
                        </div>
                        
                        <div style="background-color: #e7f3ff; border: 1px solid #b3d9ff; border-radius: 5px; padding: 15px; margin: 20px 0;">
                            <p style="margin: 0; color: #0c5460;">
                                <strong>⚠️ Action Required:</strong> Please review this transfer request as soon as possible. 
                                Click the button above to access your dashboard and approve or reject this transfer.
                            </p>
                        </div>
                        
                        <hr style="border: none; border-top: 1px solid #e9ecef; margin: 25px 0;">
                        
                        <div style="color: #6c757d; font-size: 14px;">
                            <p><strong>Alternative Access:</strong></p>
                            <p>If the button doesn't work, copy and paste this link into your browser:</p>
                            <p style="background-color: #f8f9fa; padding: 10px; border-radius: 4px; word-break: break-all;">
                                {approval_link}
                            </p>
                            
                            <p style="margin-top: 20px;">
                                <strong>Need Help?</strong> Contact the system administrator if you experience any issues accessing the approval dashboard.
                            </p>
                        </div>
                        
                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e9ecef; text-align: center; color: #6c757d; font-size: 12px;">
                            <p>This is an automated message from Bluemen Cafe Management System.</p>
                            <p>Please do not reply to this email.</p>
                        </div>
                        
                    </body>
                    </html>
                    """,
                    text_content=f"""
                    Transfer Request Approval Required
                    
                    A new transfer request requires your approval:
                    
                    Transfer Number: {transfer.transfer_number}
                    From Location: {transfer.from_location.name}
                    To Location: {transfer.to_location.name}
                    Transfer Date: {transfer.transfer_date.strftime('%B %d, %Y') if hasattr(transfer.transfer_date, 'strftime') else transfer.transfer_date}
                    Items Count: {len(transfer.items)} items
                    
                    To approve this transfer, please visit:
                    {approval_link}
                    
                    Please review and approve this transfer request in your task dashboard as soon as possible.
                    
                    ---
                    This is an automated message from Bluemen Cafe Management System.
                    """
                )
                
                # Send real-time UI notification
                await notification_service.send_real_time_notification(
                    user_id=user.id,
                    notification_type="TASK_ASSIGNED",
                    title="New Transfer Approval Task",
                    message=f"Transfer Request {transfer.transfer_number} requires your approval",
                    data={
                        "task_id": task.id,
                        "transfer_id": transfer.id,
                        "from_location": transfer.from_location.name,
                        "to_location": transfer.to_location.name
                    }
                )
        
        return task
        # endregion

    async def create_shipment_tasks(self, shipment: Shipment, user_id: int):
        """Create tasks related to shipment"""          
        # Create delivery task for driver
        if shipment.driver_id:
            await self.automation_service.create_shipment_delivery_task(
                shipment_id=shipment.id,
                driver_id=shipment.driver_id,
                user_id=user_id or 1
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