from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.base import BaseModel
from app.models.shared.enums import MessageRole

class ChatConversation(BaseModel):
    __tablename__ = 'chat_conversations'
    
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String(255), nullable=False)
    session_id = Column(String(100), nullable=True, index=True)  # For grouping related chats
    is_active = Column(Boolean, default=True)
    last_message_at = Column(DateTime(timezone=True))
    message_count = Column(Integer, default=0)
    
    # Relationships
    user = relationship("User")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ChatConversation {self.id}: {self.title[:30]}...>"
    


class ChatMessage(BaseModel):
    __tablename__ = 'chat_messages'
    
    conversation_id = Column(Integer, ForeignKey('chat_conversations.id'), nullable=False)
    role = Column(SQLEnum(MessageRole), nullable=False)  # user, assistant
    message = Column(Text, nullable=False)
    chat_metadata = Column(Text)  # JSON string for additional data like tokens, model used, etc.
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime(timezone=True))
    
    # Relationships
    conversation = relationship("ChatConversation", back_populates="messages")
    
    def __repr__(self):
        return f"<ChatMessage {self.id}: {self.role} - {self.message[:30]}...>"