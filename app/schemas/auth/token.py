from typing import Optional
from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenPayload(BaseModel):
    sub: Optional[str] = None  # user_id
    exp: Optional[int] = None
    iat: Optional[int] = None
    jti: Optional[str] = None  # JWT ID
    type: Optional[str] = None  # access or refresh

class RefreshTokenRequest(BaseModel):
    refresh_token: str