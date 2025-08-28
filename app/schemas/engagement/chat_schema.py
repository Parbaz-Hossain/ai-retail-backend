from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from app.models.shared.enums import MessageRole

class ChatMessageBase(BaseModel):
    role: MessageRole
    message: str = Field(..., min_length=1, max_length=10000)
    chat_metadata: Optional[str] = None

class ChatMessageCreate(ChatMessageBase):
    @validator('message')
    def validate_message(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Message cannot be empty')
        return v.strip()

class ChatMessageResponse(ChatMessageBase):
    id: int
    conversation_id: int
    is_edited: Optional[bool] = None
    edited_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ChatConversationBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    session_id: Optional[str] = Field(None, max_length=100)

class ChatConversationCreate(ChatConversationBase):
    initial_message: Optional[ChatMessageCreate] = None
    
    @validator('title')
    def validate_title(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Title cannot be empty')
        return v.strip()

class ChatConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None

class ChatConversationResponse(ChatConversationBase):
    id: int
    user_id: int
    is_active: bool
    last_message_at: Optional[datetime] = None
    message_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ChatConversationWithMessages(ChatConversationResponse):
    messages: List[ChatMessageResponse] = []

class ChatConversationListResponse(BaseModel):
    conversations: List[ChatConversationResponse]
    total: int
    page: int
    limit: int
    has_next: bool

class AddMessageRequest(BaseModel):
    message: ChatMessageCreate
    auto_generate_title: bool = Field(default=True, description="Auto-generate title from first message")

class ChatStats(BaseModel):
    total_conversations: int
    active_conversations: int
    total_messages: int
    messages_today: int
    avg_messages_per_conversation: float