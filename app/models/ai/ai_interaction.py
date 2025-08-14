from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class AIInteraction(BaseModel):
    __tablename__ = 'ai_interactions'
    
    session_id = Column(String(100), nullable=False)
    interaction_type = Column(String(50), nullable=False)  # VOICE, TEXT
    user_input = Column(Text, nullable=False)
    processed_input = Column(Text)  # Cleaned/processed version
    ai_response = Column(Text, nullable=False)
    intent = Column(String(100))  # Detected intent
    entities = Column(JSON)  # Extracted entities
    confidence_score = Column(Numeric(3, 2))
    action_taken = Column(String(100))  # What action was performed
    reference_type = Column(String(50))  # Related entity type
    reference_id = Column(Integer)  # Related entity ID
    user_id = Column(Integer)  # User if authenticated
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    processing_time_ms = Column(Integer)