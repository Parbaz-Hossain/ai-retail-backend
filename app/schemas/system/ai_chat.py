from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

class VoiceRequest(BaseModel):
    audio_data: bytes
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    agent: str
    timestamp: datetime
    context: Optional[Dict[str, Any]] = None
    actions_taken: Optional[List[Dict[str, Any]]] = None
    audio_response: Optional[bytes] = None