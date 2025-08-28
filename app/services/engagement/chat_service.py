import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from app.models.engagement.chat import ChatConversation, ChatMessage
from app.models.shared.enums import MessageRole
from app.schemas.engagement.chat_schema import (
    ChatConversationCreate, ChatConversationUpdate, ChatConversationResponse,
    ChatMessageCreate, ChatMessageResponse, ChatConversationWithMessages
)

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- Conversation Methods ----------
    async def create_conversation(
        self, 
        data: ChatConversationCreate, 
        user_id: int
    ) -> ChatConversation:
        """Create a new chat conversation"""
        try:
            conversation = ChatConversation(
                user_id=user_id,
                title=data.title,
                session_id=data.session_id,
                is_active=True,
                message_count=0,
                created_by=user_id
            )
            
            self.session.add(conversation)
            await self.session.flush()
            
            # Add initial message if provided
            if data.initial_message:
                await self._add_message_to_conversation(
                    conversation.id, data.initial_message, auto_commit=False
                )
            
            await self.session.commit()
            await self.session.refresh(conversation)
            
            logger.info(f"Chat conversation created: {conversation.id} by user {user_id}")
            return conversation
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating conversation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating conversation"
            )

    async def get_conversation(
        self, 
        conversation_id: int, 
        user_id: int, 
        include_messages: bool = False
    ) -> Optional[ChatConversation]:
        """Get a conversation by ID"""
        try:
            query = select(ChatConversation).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
                ChatConversation.is_deleted == False
            )
            
            if include_messages:
                query = query.options(
                    selectinload(ChatConversation.messages).options(
                        selectinload(ChatMessage.conversation)
                    )
                )
            
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting conversation {conversation_id}: {e}")
            return None

    async def get_user_conversations(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        session_id: Optional[str] = None
    ) -> List[ChatConversation]:
        """Get user's conversations with filters"""
        try:
            query = select(ChatConversation).where(
                ChatConversation.user_id == user_id,
                ChatConversation.is_deleted == False
            )
            
            if is_active is not None:
                query = query.where(ChatConversation.is_active == is_active)
            if session_id:
                query = query.where(ChatConversation.session_id == session_id)
            if search:
                like = f"%{search}%"
                query = query.where(ChatConversation.title.ilike(like))
            
            query = query.order_by(desc(ChatConversation.last_message_at))
            result = await self.session.execute(query.offset(skip).limit(limit))
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting user conversations: {e}")
            return []

    async def count_user_conversations(
        self,
        user_id: int,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        session_id: Optional[str] = None
    ) -> int:
        """Count user's conversations"""
        try:
            query = select(func.count(ChatConversation.id)).where(
                ChatConversation.user_id == user_id,
                ChatConversation.is_deleted == False
            )
            
            if is_active is not None:
                query = query.where(ChatConversation.is_active == is_active)
            if session_id:
                query = query.where(ChatConversation.session_id == session_id)
            if search:
                like = f"%{search}%"
                query = query.where(ChatConversation.title.ilike(like))
            
            result = await self.session.execute(query)
            return int(result.scalar() or 0)
            
        except Exception as e:
            logger.error(f"Error counting user conversations: {e}")
            return 0

    async def update_conversation(
        self, 
        conversation_id: int, 
        data: ChatConversationUpdate, 
        user_id: int
    ) -> Optional[ChatConversation]:
        """Update a conversation"""
        try:
            result = await self.session.execute(
                select(ChatConversation).where(
                    ChatConversation.id == conversation_id,
                    ChatConversation.user_id == user_id,
                    ChatConversation.is_deleted == False
                )
            )
            
            conversation = result.scalar_one_or_none()
            if not conversation:
                return None
            
            for field, value in data.dict(exclude_unset=True).items():
                setattr(conversation, field, value)
            
            conversation.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(conversation)
            
            logger.info(f"Conversation updated: {conversation.id} by user {user_id}")
            return conversation
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating conversation {conversation_id}: {e}")
            return None

    async def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Soft delete a conversation"""
        try:
            result = await self.session.execute(
                select(ChatConversation).where(
                    ChatConversation.id == conversation_id,
                    ChatConversation.user_id == user_id,
                    ChatConversation.is_deleted == False
                )
            )
            
            conversation = result.scalar_one_or_none()
            if not conversation:
                return False
            
            conversation.is_deleted = True
            conversation.is_active = False
            await self.session.commit()
            
            logger.info(f"Conversation deleted: {conversation.id} by user {user_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting conversation {conversation_id}: {e}")
            return False

    # ---------- Message Methods ----------
    async def add_message(
        self, 
        conversation_id: int, 
        message_data: ChatMessageCreate, 
        user_id: int,
        auto_generate_title: bool = False
    ) -> Optional[ChatMessage]:
        """Add a message to a conversation"""
        try:
            # Verify conversation exists and belongs to user
            conversation = await self.get_conversation(conversation_id, user_id)
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
            
            message = await self._add_message_to_conversation(
                conversation_id, message_data, auto_commit=True
            )
            
            # Auto-generate title from first user message if needed
            if (auto_generate_title and 
                message_data.role == MessageRole.USER and 
                conversation.message_count <= 1):
                await self._auto_generate_title(conversation, message_data.message)
            
            return message
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error adding message: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error adding message"
            )

    async def _add_message_to_conversation(
        self, 
        conversation_id: int, 
        message_data: ChatMessageCreate,
        auto_commit: bool = True
    ) -> ChatMessage:
        """Internal method to add message to conversation"""
        message = ChatMessage(
            conversation_id=conversation_id,
            role=message_data.role,
            message=message_data.message,
            chat_metadata=message_data.chat_metadata,
            created_by = message_data.created_by
        )
        
        self.session.add(message)
        
        # Update conversation stats
        result = await self.session.execute(
            select(ChatConversation).where(ChatConversation.id == conversation_id)
        )
        conversation = result.scalar_one()
        conversation.message_count = (conversation.message_count or 0) + 1
        conversation.last_message_at = datetime.utcnow()
        
        if auto_commit:
            await self.session.flush()
            await self.session.commit()
            await self.session.refresh(message)
        
        return message

    async def _auto_generate_title(self, conversation: ChatConversation, message: str):
        """Auto-generate conversation title from first message"""
        try:
            # Use first 50 characters of the message as title
            title = message[:50].strip()
            if len(message) > 50:
                title += "..."
            
            conversation.title = title
            await self.session.commit()
            
        except Exception as e:
            logger.error(f"Error auto-generating title: {e}")

    async def get_conversation_messages(
        self,
        conversation_id: int,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[ChatMessage]:
        """Get messages for a conversation"""
        try:
            # Verify conversation belongs to user
            conversation = await self.get_conversation(conversation_id, user_id)
            if not conversation:
                return []
            
            result = await self.session.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.conversation_id == conversation_id,
                    ChatMessage.is_deleted == False
                )
                .order_by(ChatMessage.created_at)
                .offset(skip)
                .limit(limit)
            )
            
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting conversation messages: {e}")
            return []

    async def update_message(
        self, 
        message_id: int, 
        new_message: str, 
        user_id: int
    ) -> Optional[ChatMessage]:
        """Update a message (only user messages can be edited)"""
        try:
            # Get message with conversation to verify user ownership
            result = await self.session.execute(
                select(ChatMessage)
                .join(ChatConversation)
                .where(
                    ChatMessage.id == message_id,
                    ChatConversation.user_id == user_id,
                    ChatMessage.role == MessageRole.USER,  # Only user messages can be edited
                    ChatMessage.is_deleted == False
                )
            )
            
            message = result.scalar_one_or_none()
            if not message:
                return None
            
            message.message = new_message.strip()
            message.is_edited = True
            message.edited_at = datetime.utcnow()
            message.updated_at = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(message)
            
            return message
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating message {message_id}: {e}")
            return None

    # ---------- Stats ----------
    async def get_chat_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user's chat statistics"""
        try:
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Total conversations
            total_conv_result = await self.session.execute(
                select(func.count(ChatConversation.id)).where(
                    ChatConversation.user_id == user_id,
                    ChatConversation.is_deleted == False
                )
            )
            total_conversations = int(total_conv_result.scalar() or 0)

            # Active conversations
            active_conv_result = await self.session.execute(
                select(func.count(ChatConversation.id)).where(
                    ChatConversation.user_id == user_id,
                    ChatConversation.is_active == True,
                    ChatConversation.is_deleted == False
                )
            )
            active_conversations = int(active_conv_result.scalar() or 0)

            # Total messages
            total_msg_result = await self.session.execute(
                select(func.count(ChatMessage.id))
                .join(ChatConversation)
                .where(
                    ChatConversation.user_id == user_id,
                    ChatMessage.is_deleted == False
                )
            )
            total_messages = int(total_msg_result.scalar() or 0)

            # Messages today
            today_msg_result = await self.session.execute(
                select(func.count(ChatMessage.id))
                .join(ChatConversation)
                .where(
                    ChatConversation.user_id == user_id,
                    ChatMessage.created_at >= today,
                    ChatMessage.is_deleted == False
                )
            )
            messages_today = int(today_msg_result.scalar() or 0)

            # Average messages per conversation
            avg_messages = total_messages / total_conversations if total_conversations > 0 else 0

            return {
                "total_conversations": total_conversations,
                "active_conversations": active_conversations,
                "total_messages": total_messages,
                "messages_today": messages_today,
                "avg_messages_per_conversation": round(avg_messages, 2)
            }

        except Exception as e:
            logger.error(f"Error getting chat stats: {e}")
            return {
                "total_conversations": 0,
                "active_conversations": 0,
                "total_messages": 0,
                "messages_today": 0,
                "avg_messages_per_conversation": 0.0
            }