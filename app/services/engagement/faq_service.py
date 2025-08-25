import logging
from typing import Optional, List
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc
from app.models.engagement.faq import FAQ
from app.schemas.engagement.faq_schema import FAQCreate, FAQUpdate

logger = logging.getLogger(__name__)

class FAQService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- Getters ----------
    async def get_faq(self, faq_id: int, user_id: int) -> Optional[FAQ]:
        try:
            result = await self.session.execute(
                select(FAQ).where(
                    FAQ.id == faq_id,
                    FAQ.user_id == user_id,
                    FAQ.is_deleted == False
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting FAQ {faq_id}: {e}")
            return None

    async def get_public_faq(self, faq_id: int) -> Optional[FAQ]:
        try:
            result = await self.session.execute(
                select(FAQ).where(
                    FAQ.id == faq_id,
                    FAQ.is_public == True,
                    FAQ.is_active == True,
                    FAQ.is_deleted == False
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting public FAQ {faq_id}: {e}")
            return None

    # ---------- Create / Update / Delete ----------
    async def create_faq(self, data: FAQCreate, user_id: int) -> FAQ:
        try:
            faq = FAQ(
                user_id=user_id,
                question=data.question,
                answer=data.answer,
                category=data.category,
                tags=data.tags,
                priority=data.priority,
                is_public=data.is_public,
                is_active=True
            )
            self.session.add(faq)
            await self.session.flush()
            await self.session.commit()
            await self.session.refresh(faq)
            logger.info(f"FAQ created: {faq.id} by user {user_id}")
            return faq
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating FAQ: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Error creating FAQ"
            )

    async def update_faq(self, faq_id: int, data: FAQUpdate, user_id: int) -> Optional[FAQ]:
        try:
            faq = await self.get_faq(faq_id, user_id)
            if not faq:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail="FAQ not found"
                )

            for field, value in data.dict(exclude_unset=True).items():
                setattr(faq, field, value)

            faq.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(faq)
            logger.info(f"FAQ updated: {faq.id} by user {user_id}")
            return faq
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating FAQ {faq_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Error updating FAQ"
            )

    async def delete_faq(self, faq_id: int, user_id: int) -> bool:
        try:
            faq = await self.get_faq(faq_id, user_id)
            if not faq:
                return False

            faq.is_deleted = True
            faq.updated_at = datetime.utcnow()
            await self.session.commit()
            logger.info(f"FAQ deleted: {faq.id} by user {user_id}")
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting FAQ {faq_id}: {e}")
            return False

    # ---------- Listing & Search ----------
    async def get_user_faqs(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[FAQ]:
        try:
            query = select(FAQ).where(
                FAQ.user_id == user_id,
                FAQ.is_deleted == False
            )
            
            if is_active is not None:
                query = query.where(FAQ.is_active == is_active)
            if category:
                query = query.where(FAQ.category == category)
            if search:
                like = f"%{search}%"
                query = query.where(
                    or_(
                        FAQ.question.ilike(like),
                        FAQ.answer.ilike(like),
                        FAQ.tags.ilike(like)
                    )
                )
            
            query = query.order_by(desc(FAQ.priority), desc(FAQ.created_at))
            result = await self.session.execute(query.offset(skip).limit(limit))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting user FAQs: {e}")
            return []

    async def count_user_faqs(
        self,
        user_id: int,
        search: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> int:
        try:
            query = select(func.count(FAQ.id)).where(
                FAQ.user_id == user_id,
                FAQ.is_deleted == False
            )
            
            if is_active is not None:
                query = query.where(FAQ.is_active == is_active)
            if category:
                query = query.where(FAQ.category == category)
            if search:
                like = f"%{search}%"
                query = query.where(
                    or_(
                        FAQ.question.ilike(like),
                        FAQ.answer.ilike(like),
                        FAQ.tags.ilike(like)
                    )
                )
            
            result = await self.session.execute(query)
            return int(result.scalar() or 0)
        except Exception as e:
            logger.error(f"Error counting user FAQs: {e}")
            return 0

    async def increment_view_count(self, faq_id: int):
        try:
            result = await self.session.execute(
                select(FAQ).where(FAQ.id == faq_id)
            )
            faq = result.scalar_one_or_none()
            if faq:
                faq.view_count = (faq.view_count or 0) + 1
                faq.last_viewed_at = datetime.utcnow()
                await self.session.commit()
        except Exception as e:
            logger.error(f"Error incrementing view count: {e}")

    async def get_categories(self, user_id: int) -> List[str]:
        try:
            result = await self.session.execute(
                select(FAQ.category).where(
                    FAQ.user_id == user_id,
                    FAQ.is_deleted == False,
                    FAQ.category.is_not(None)
                ).distinct()
            )
            return [row[0] for row in result.fetchall() if row[0]]
        except Exception as e:
            logger.error(f"Error getting FAQ categories: {e}")
            return []