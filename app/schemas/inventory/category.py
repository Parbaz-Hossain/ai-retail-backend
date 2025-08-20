from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    is_active: Optional[bool] = None

class CategoryInDB(CategoryBase):
    id: int
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True

# Shallow reference used for parent/children to avoid deep recursion
class CategoryRef(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None

    class Config:
        from_attributes = True

# Final response model
class Category(CategoryInDB):
    parent: Optional[CategoryRef] = None
    children: List[CategoryRef] = Field(default_factory=list)
