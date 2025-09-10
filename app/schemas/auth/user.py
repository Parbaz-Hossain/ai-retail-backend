from typing import Optional, List
from fastapi import Form
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime

from app.schemas.auth.role import Role

class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    phone: Optional[str] = None
    address: Optional[str] = None

    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').isalnum():
            raise ValueError('Username must be alphanumeric (underscores allowed)')
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        return v

class UserCreate(UserBase):
    password: str
    confirm_password: str

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
class UserCreateForm:
    def __init__(
        self,
        email: str = Form(...),
        username: str = Form(...),
        full_name: str = Form(...),
        password: str = Form(...),
        confirm_password: str = Form(...),
        phone: Optional[str] = Form(None),
        address: Optional[str] = Form(None)
    ):
        self.email = email
        self.username = username
        self.full_name = full_name
        self.password = password
        self.confirm_password = confirm_password
        self.phone = phone
        self.address = address
    
    def to_user_create(self) -> UserCreate:
        """Convert form data to UserCreate schema"""
        return UserCreate(
            email=self.email,
            username=self.username,
            full_name=self.full_name,
            password=self.password,
            confirm_password=self.confirm_password,
            phone=self.phone,
            address=self.address
        )

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    profile_image: Optional[str] = None

class UserInDBBase(UserBase):
    id: int
    profile_image: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_superuser: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

class User(UserInDBBase):
    roles: List['Role'] = []

class UserInDB(UserInDBBase):
    hashed_password: str

class UserResponse(UserInDBBase):
    roles: List['Role'] = []