from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.services.notification.notification_service import NotificationService
from app.models.auth import User

router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, db: AsyncSession = Depends(get_async_session)):
    """WebSocket endpoint for real-time notifications"""
    await websocket.accept()
    
    notification_service = NotificationService(db)
    notification_service.add_connection(user_id, websocket)
    
    try:
        while True:
            # Keep connection alive and listen for client messages
            data = await websocket.receive_text()
            # Handle ping/pong or other client messages if needed
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        notification_service.remove_connection(user_id, websocket)

@router.get("/")
async def get_notifications(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    limit: int = 50
):
    """Get user's notifications"""
    notification_service = NotificationService(db)
    notifications = await notification_service.get_user_notifications(current_user.id, limit)
    
    return {
        "notifications": notifications,
        "total": len(notifications)
    }

@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Mark notification as read"""
    notification_service = NotificationService(db)
    success = await notification_service.mark_notification_read(notification_id, current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Notification marked as read"}

@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get count of unread notifications"""
    from app.models.alerts.notification_queue import NotificationQueue
    from sqlalchemy import select, func, and_
    
    result = await db.execute(
        select(func.count())
        .select_from(NotificationQueue)
        .where(
            and_(
                NotificationQueue.recipient_id == current_user.id,
                NotificationQueue.notification_type == "UI_NOTIFICATION",
                NotificationQueue.status == "PENDING"
            )
        )
    )
    count = result.scalar()
    
    return {"unread_count": count}