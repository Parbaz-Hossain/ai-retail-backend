import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from app.models.engagement.user_history import UserHistory
from app.models.shared.enums import HistoryActionType
from app.schemas.engagement.user_history_schema import UserHistoryCreate

logger = logging.getLogger(__name__)

class UserHistoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- Create History ----------
    async def create_history(
        self, 
        data: UserHistoryCreate, 
        user_id: int, 
        auto_commit: bool = True
    ) -> UserHistory:
        try:
            history = UserHistory(
                user_id=user_id,
                action_type=data.action_type,
                resource_type=data.resource_type,
                resource_id=data.resource_id,
                title=data.title,
                description=data.description,
                metadata=data.metadata,
                session_id=data.session_id,
                ip_address=data.ip_address,
                user_agent=data.user_agent
            )
            self.session.add(history)
            if auto_commit:
                await self.session.flush()
                await self.session.commit()
                await self.session.refresh(history)
            return history
        except Exception as e:
            if auto_commit:
                await self.session.rollback()
            logger.error(f"Error creating history: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Error creating history"
            )

    # ---------- Quick Log Methods ----------
    async def log_action(
        self,
        user_id: int,
        action_type: HistoryActionType,
        resource_type: str,
        title: str,
        resource_id: Optional[int] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> UserHistory:
        data = UserHistoryCreate(
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            title=title,
            description=description,
            metadata=metadata,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        return await self.create_history(data, user_id)

    # ---------- Getters ----------
    async def get_user_histories(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        action_type: Optional[HistoryActionType] = None,
        resource_type: Optional[str] = None,
        is_favorite: Optional[bool] = None,
        is_archived: Optional[bool] = False,
        session_id: Optional[str] = None
    ) -> List[UserHistory]:
        try:
            query = select(UserHistory).where(
                UserHistory.user_id == user_id,
                UserHistory.is_deleted == False
            )
            
            if action_type:
                query = query.where(UserHistory.action_type == action_type)
            if resource_type:
                query = query.where(UserHistory.resource_type == resource_type)
            if is_favorite is not None:
                query = query.where(UserHistory.is_favorite == is_favorite)
            if is_archived is not None:
                query = query.where(UserHistory.is_archived == is_archived)
            if session_id:
                query = query.where(UserHistory.session_id == session_id)
            
            query = query.order_by(desc(UserHistory.created_at))
            result = await self.session.execute(query.offset(skip).limit(limit))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting user histories: {e}")
            return []

    async def count_user_histories(
        self,
        user_id: int,
        action_type: Optional[HistoryActionType] = None,
        resource_type: Optional[str] = None,
        is_favorite: Optional[bool] = None,
        is_archived: Optional[bool] = False,
        session_id: Optional[str] = None
    ) -> int:
        try:
            query = select(func.count(UserHistory.id)).where(
                UserHistory.user_id == user_id,
                UserHistory.is_deleted == False
            )
            
            if action_type:
                query = query.where(UserHistory.action_type == action_type)
            if resource_type:
                query = query.where(UserHistory.resource_type == resource_type)
            if is_favorite is not None:
                query = query.where(UserHistory.is_favorite == is_favorite)
            if is_archived is not None:
                query = query.where(UserHistory.is_archived == is_archived)
            if session_id:
                query = query.where(UserHistory.session_id == session_id)
            
            result = await self.session.execute(query)
            return int(result.scalar() or 0)
        except Exception as e:
            logger.error(f"Error counting user histories: {e}")
            return 0

    # ---------- Update Operations ----------
    async def toggle_favorite(self, history_id: int, user_id: int) -> bool:
        try:
            result = await self.session.execute(
                select(UserHistory).where(
                    UserHistory.id == history_id,
                    UserHistory.user_id == user_id,
                    UserHistory.is_deleted == False
                )
            )
            history = result.scalar_one_or_none()
            if not history:
                return False
            
            history.is_favorite = not history.is_favorite
            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error toggling favorite: {e}")
            return False

    async def archive_history(self, history_id: int, user_id: int) -> bool:
        try:
            result = await self.session.execute(
                select(UserHistory).where(
                    UserHistory.id == history_id,
                    UserHistory.user_id == user_id,
                    UserHistory.is_deleted == False
                )
            )
            history = result.scalar_one_or_none()
            if not history:
                return False
            
            history.is_archived = True
            history.archived_at = datetime.utcnow()
            await self.session.commit()
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error archiving history: {e}")
            return False

    # ---------- Stats ----------
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        try:
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)

            # Total actions
            total_result = await self.session.execute(
                select(func.count(UserHistory.id)).where(
                    UserHistory.user_id == user_id,
                    UserHistory.is_deleted == False
                )
            )
            total = int(total_result.scalar() or 0)

            # Today's actions
            today_result = await self.session.execute(
                select(func.count(UserHistory.id)).where(
                    UserHistory.user_id == user_id,
                    UserHistory.created_at >= today,
                    UserHistory.is_deleted == False
                )
            )
            today_count = int(today_result.scalar() or 0)

            # This week
            week_result = await self.session.execute(
                select(func.count(UserHistory.id)).where(
                    UserHistory.user_id == user_id,
                    UserHistory.created_at >= week_ago,
                    UserHistory.is_deleted == False
                )
            )
            week_count = int(week_result.scalar() or 0)

            # This month
            month_result = await self.session.execute(
                select(func.count(UserHistory.id)).where(
                    UserHistory.user_id == user_id,
                    UserHistory.created_at >= month_ago,
                    UserHistory.is_deleted == False
                )
            )
            month_count = int(month_result.scalar() or 0)

            # Most used resource
            resource_result = await self.session.execute(
                select(
                    UserHistory.resource_type,
                    func.count(UserHistory.id).label('count')
                ).where(
                    UserHistory.user_id == user_id,
                    UserHistory.is_deleted == False
                ).group_by(UserHistory.resource_type).order_by(desc('count')).limit(1)
            )
            most_used = resource_result.first()
            most_used_resource = most_used[0] if most_used else "None"

            # Favorites count
            fav_result = await self.session.execute(
                select(func.count(UserHistory.id)).where(
                    UserHistory.user_id == user_id,
                    UserHistory.is_favorite == True,
                    UserHistory.is_deleted == False
                )
            )
            favorite_count = int(fav_result.scalar() or 0)

            return {
                "total_actions": total,
                "actions_today": today_count,
                "actions_this_week": week_count,
                "actions_this_month": month_count,
                "most_used_resource": most_used_resource,
                "favorite_count": favorite_count
            }
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {
                "total_actions": 0,
                "actions_today": 0,
                "actions_this_week": 0,
                "actions_this_month": 0,
                "most_used_resource": "None",
                "favorite_count": 0
            }