from typing import Optional
from pydantic import BaseModel, EmailStr

from app.schemas.auth.user import User, UserResponse

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str
    confirm_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

class OtpInput(BaseModel):
    otp: str

class ForgotInitInput(BaseModel):
    email: EmailStr

class ResetInput(BaseModel):
    new_password: str