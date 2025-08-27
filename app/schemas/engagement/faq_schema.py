from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime

class FAQBase(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)
    answer: str = Field(..., min_length=5, max_length=5000)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = Field(None, max_length=500)
    priority: int = Field(default=0, ge=0, le=10)
    is_public: bool = Field(default=False)

class FAQCreate(FAQBase):
    @validator('question')
    def validate_question(cls, v):
        if not v or len(v.strip()) < 5:
            raise ValueError('Question must be at least 5 characters')
        return v.strip()
    
    @validator('answer')
    def validate_answer(cls, v):
        if not v or len(v.strip()) < 5:
            raise ValueError('Answer must be at least 5 characters')
        return v.strip()

class FAQUpdate(BaseModel):
    question: Optional[str] = Field(None, min_length=5, max_length=1000)
    answer: Optional[str] = Field(None, min_length=5, max_length=5000)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = Field(None, max_length=500)
    priority: Optional[int] = Field(None, ge=0, le=10)
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None

class FAQResponse(FAQBase):
    id: int
    user_id: int
    is_active: bool
    view_count: Optional[int] = None
    last_viewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class FAQListResponse(BaseModel):
    faqs: List[FAQResponse]
    total: int
    page: int
    limit: int
    has_next: bool