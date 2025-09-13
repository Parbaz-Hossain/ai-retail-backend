import asyncio
from datetime import datetime
import json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.api.dependencies import get_current_user
from app.services.notification.notification_service import NotificationService
from app.models.auth import User

import traceback

router = APIRouter()


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    notification_service: NotificationService | None = None
    try:
        # Accept connection
        await websocket.accept()
        print(f"✅ WebSocket connection accepted for user {user_id}")

        # Test DB connection
        try:
            await db.execute(text("SELECT 1"))
            print(f"✅ Database connection OK for user {user_id}")
        except Exception as db_error:
            print(f"❌ Database connection failed for user {user_id}: {db_error}")
            await websocket.close(code=1011, reason="Database connection failed")
            return

        # Register user’s connection in service
        notification_service = NotificationService(db)
        notification_service.add_connection(user_id, websocket)
        print(f"✅ NotificationService initialized for user {user_id}")

        # Tell client "you are connected"
        await websocket.send_text(
            json.dumps(
                {
                    "type": "welcome",
                    "message": f"WebSocket connected for user {user_id}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        )

        # Main receive loop
        while True:
            try:
                message = await websocket.receive()

                if message["type"] == "websocket.receive":
                    if "text" in message:
                        data = message["text"]
                        print(f"📨 Received from user {user_id}: {data}")

                        if data == "ping":
                            await websocket.send_text("pong")
                        elif data == "get_notifications":
                            notifications = await notification_service.get_user_notifications(
                                user_id, 10
                            )
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "notifications_list",
                                        "data": notifications,
                                    }
                                )
                            )
                        else:
                            # echo back generic text
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "echo",
                                        "data": data,
                                        "timestamp": datetime.utcnow().isoformat(),
                                    }
                                )
                            )

                    elif "bytes" in message:
                        print(f"📨 Received bytes from user {user_id}")

                elif message["type"] == "websocket.disconnect":
                    print(f"🔌 Client disconnected normally for user {user_id}")
                    break

            except WebSocketDisconnect:
                print(f"🔌 WebSocket disconnected for user {user_id}")
                break
            except Exception as msg_error:
                print(f"❌ Error in message loop for user {user_id}: {msg_error}")
                print(traceback.format_exc())
                break

    except Exception as e:
        print(f"❌ Fatal WebSocket error for user {user_id}: {e}")
        print(traceback.format_exc())
    finally:
        if notification_service:
            try:
                notification_service.remove_connection(user_id, websocket)
                print(f"🧹 Cleaned up connection for user {user_id}")
            except Exception as cleanup_error:
                print(f"❌ Cleanup error for user {user_id}: {cleanup_error}")


# -----------------------
# REST Endpoints
# -----------------------

@router.get("/")
async def get_notifications(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
    limit: int = 50,
):
    """Get user's notifications"""
    notification_service = NotificationService(db)
    notifications = await notification_service.get_user_notifications(
        current_user.id, limit
    )

    return {"notifications": notifications, "total": len(notifications)}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Mark notification as read"""
    notification_service = NotificationService(db)
    success = await notification_service.mark_notification_read(
        notification_id, current_user.id
    )

    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"message": "Notification marked as read"}


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
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
                NotificationQueue.status == "PENDING",
            )
        )
    )
    count = result.scalar()

    return {"unread_count": count}
