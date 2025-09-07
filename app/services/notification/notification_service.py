import json
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
from app.models.alerts.notification_queue import NotificationQueue

class NotificationService:
    """Service for real-time UI notifications"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        # In-memory storage for WebSocket connections
        self._connections: Dict[int, list] = {}  # user_id: [websocket_connections]
    
    async def send_real_time_notification(
        self, 
        user_id: int, 
        notification_type: str,
        title: str, 
        message: str, 
        data: Optional[Dict[str, Any]] = None
    ):
        """Send real-time notification to user"""
        
        # Store notification in database
        notification = NotificationQueue(
            notification_type="UI_NOTIFICATION",
            recipient_id=user_id,
            subject=title,
            message=message,
            template_data=data or {},
            priority=1,
            status="PENDING",
            reference_type=notification_type,
            # created_by=1  # System user
        )
        
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        
        # Send to connected WebSocket clients
        if user_id in self._connections:
            notification_data = {
                "id": notification.id,
                "type": notification_type,
                "title": title,
                "message": message,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat(),
                "read": False
            }
            
            # Send to all user's connected clients
            for websocket in self._connections[user_id]:
                try:
                    await websocket.send_text(json.dumps(notification_data))
                except Exception:
                    # Remove disconnected websocket
                    self._connections[user_id].remove(websocket)
        
        return notification
    
    def add_connection(self, user_id: int, websocket):
        """Add WebSocket connection for user"""
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
    
    def remove_connection(self, user_id: int, websocket):
        """Remove WebSocket connection for user"""
        if user_id in self._connections:
            if websocket in self._connections[user_id]:
                self._connections[user_id].remove(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
    
    async def get_user_notifications(self, user_id: int, limit: int = 50) -> list:
        """Get user's recent notifications"""
        result = await self.db.execute(
            select(NotificationQueue)
            .where(
                and_(
                    NotificationQueue.recipient_id == user_id,
                    NotificationQueue.notification_type == "UI_NOTIFICATION"
                )
            )
            .order_by(NotificationQueue.created_at.desc())
            .limit(limit)
        )
        notifications = result.scalars().all()
        
        return [
            {
                "id": notif.id,
                "type": notif.reference_type,
                "title": notif.subject,
                "message": notif.message,
                "data": notif.template_data or {},
                "timestamp": notif.created_at.isoformat(),
                "read": notif.status == "SENT"
            }
            for notif in notifications
        ]
    
    async def mark_notification_read(self, notification_id: int, user_id: int):
        """Mark notification as read"""
        result = await self.db.execute(
            select(NotificationQueue)
            .where(
                and_(
                    NotificationQueue.id == notification_id,
                    NotificationQueue.recipient_id == user_id
                )
            )
        )
        notification = result.scalar_one_or_none()
        
        if notification:
            notification.status = "SENT"
            await self.db.commit()
            return True
        return False