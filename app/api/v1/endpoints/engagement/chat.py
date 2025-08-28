import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_async_session
from app.models.auth.user import User
from app.services.engagement.chat_service import ChatService
from app.services.engagement.user_history_service import UserHistoryService
from app.schemas.engagement.chat_schema import (
    ChatConversationCreate, ChatConversationUpdate, ChatConversationResponse,
    ChatConversationWithMessages, ChatConversationListResponse,
    ChatMessageCreate, ChatMessageResponse, AddMessageRequest, ChatStats
)
from app.models.shared.enums import HistoryActionType, MessageRole

router = APIRouter()
logger = logging.getLogger(__name__)

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host

@router.post("/conversations", response_model=ChatConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: ChatConversationCreate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new chat conversation"""
    try:
        chat_service = ChatService(session)
        history_service = UserHistoryService(session)
        
        conversation = await chat_service.create_conversation(data, current_user.id)
        
        # Log to history
        await history_service.log_action(
            user_id=current_user.id,
            action_type=HistoryActionType.CREATE,
            resource_type="CHAT_CONVERSATION",
            resource_id=conversation.id,
            title=f"Created chat: {data.title}",
            session_id=data.session_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        
        return ChatConversationResponse.model_validate(conversation, from_attributes=True)
        
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating conversation"
        )

@router.get("/conversations/{conversation_id}", response_model=ChatConversationWithMessages)
async def get_conversation(
    conversation_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Get a conversation with all its messages"""
    try:
        chat_service = ChatService(session)
        history_service = UserHistoryService(session)
        
        conversation = await chat_service.get_conversation(
            conversation_id, current_user.id, include_messages=True
        )
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Log to history
        await history_service.log_action(
            user_id=current_user.id,
            action_type=HistoryActionType.VIEW,
            resource_type="CHAT_CONVERSATION",
            resource_id=conversation.id,
            title=f"Viewed chat: {conversation.title}",
            session_id=conversation.session_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        
        # Convert to response model
        messages = [
            ChatMessageResponse.model_validate(msg, from_attributes=True) 
            for msg in sorted(conversation.messages, key=lambda x: x.created_at)
        ]
        
        response = ChatConversationWithMessages.model_validate(conversation, from_attributes=True)
        response.messages = messages
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving conversation"
        )

@router.post("/conversations/{conversation_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def add_message(
    conversation_id: int,
    data: AddMessageRequest,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Add a message to a conversation"""
    try:
        chat_service = ChatService(session)
        history_service = UserHistoryService(session)
        
        message = await chat_service.add_message(
            conversation_id, data.message, current_user.id, data.auto_generate_title
        )
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Log to history
        await history_service.log_action(
            user_id=current_user.id,
            action_type=HistoryActionType.CREATE,
            resource_type="CHAT_MESSAGE",
            resource_id=message.id,
            title=f"Sent {data.message.role} message",
            description=f"Message: {data.message.message[:100]}...",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        
        return ChatMessageResponse.model_validate(message, from_attributes=True)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error adding message"
        )

@router.put("/conversations/{conversation_id}", response_model=ChatConversationResponse)
async def update_conversation(
    conversation_id: int,
    data: ChatConversationUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update a conversation"""
    try:
        chat_service = ChatService(session)
        history_service = UserHistoryService(session)
        
        conversation = await chat_service.update_conversation(
            conversation_id, data, current_user.id
        )
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Log to history
        await history_service.log_action(
            user_id=current_user.id,
            action_type=HistoryActionType.UPDATE,
            resource_type="CHAT_CONVERSATION",
            resource_id=conversation.id,
            title=f"Updated chat: {conversation.title}",
            session_id=conversation.session_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )
        
        return ChatConversationResponse.model_validate(conversation, from_attributes=True)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating conversation"
        )

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a conversation"""
    try:
        chat_service = ChatService(session)
        history_service = UserHistoryService(session)
        
        # Get conversation first for logging
        conversation = await chat_service.get_conversation(conversation_id, current_user.id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        success = await chat_service.delete_conversation(conversation_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Log to history
        await history_service.log_action(
            user_id=current_user.id,
            action_type=HistoryActionType.DELETE,
            resource_type="CHAT_CONVERSATION",
            resource_id=conversation_id,
            title=f"Deleted chat: {conversation.title}",
            session_id=conversation.session_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )

        return {"detail": "Conversation deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting conversation"
        )

# region Commented Out for Future Use
# @router.get("/conversations", response_model=ChatConversationListResponse)
# async def get_conversations(
#     skip: int = Query(0, ge=0),
#     limit: int = Query(20, ge=1, le=100),
#     search: Optional[str] = Query(None),
#     is_active: Optional[bool] = Query(None),
#     session_id: Optional[str] = Query(None),
#     session: AsyncSession = Depends(get_async_session),
#     current_user: User = Depends(get_current_user)
# ):
#     """Get user's conversations with pagination and filters"""
#     try:
#         chat_service = ChatService(session)
        
#         conversations = await chat_service.get_user_conversations(
#             user_id=current_user.id,
#             skip=skip,
#             limit=limit,
#             search=search,
#             is_active=is_active,
#             session_id=session_id
#         )
        
#         total = await chat_service.count_user_conversations(
#             user_id=current_user.id,
#             search=search,
#             is_active=is_active,
#             session_id=session_id
#         )
        
#         conversation_responses = [
#             ChatConversationResponse.model_validate(conv, from_attributes=True) 
#             for conv in conversations
#         ]
        
#         return ChatConversationListResponse(
#             conversations=conversation_responses,
#             total=total,
#             page=(skip // limit) + 1,
#             limit=limit,
#             has_next=(skip + limit) < total
#         )
        
#     except Exception as e:
#         logger.error(f"Error getting conversations: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Error retrieving conversations"
#         )


# @router.get("/conversations/{conversation_id}/messages", response_model=List[ChatMessageResponse])
# async def get_conversation_messages(
#     conversation_id: int,
#     skip: int = Query(0, ge=0),
#     limit: int = Query(100, ge=1, le=200),
#     session: AsyncSession = Depends(get_async_session),
#     current_user: User = Depends(get_current_user)
# ):
#     """Get messages for a specific conversation"""
#     try:
#         chat_service = ChatService(session)
        
#         messages = await chat_service.get_conversation_messages(
#             conversation_id, current_user.id, skip, limit
#         )
        
#         return [ChatMessageResponse.model_validate(msg, from_attributes=True) for msg in messages]
        
#     except Exception as e:
#         logger.error(f"Error getting conversation messages: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Error retrieving messages"
#         )


# @router.get("/stats", response_model=ChatStats)
# async def get_chat_stats(
#     session: AsyncSession = Depends(get_async_session),
#     current_user: User = Depends(get_current_user)
# ):
#     """Get user's chat statistics"""
#     try:
#         chat_service = ChatService(session)
#         stats = await chat_service.get_chat_stats(current_user.id)
#         return ChatStats(**stats)
        
#     except Exception as e:
#         logger.error(f"Error getting chat stats: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Error retrieving statistics"
#         )
# endregion