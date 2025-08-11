from typing import Optional
from fastapi import HTTPException, status
from jose import JWTError, jwt
from datetime import datetime
from app.core.config import settings
from app.core.security import verify_token

def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate access token"""
    try:
        payload = verify_token(token)
        if payload is None:
            return None
        
        # Check token type
        if payload.get("type") != "access":
            return None
        
        # Check expiration
        exp = payload.get("exp")
        if exp is None or datetime.utcnow().timestamp() > exp:
            return None
        
        return payload
    except Exception:
        return None

def decode_refresh_token(token: str) -> Optional[dict]:
    """Decode and validate refresh token"""
    try:
        payload = verify_token(token)
        if payload is None:
            return None
        
        # Check token type
        if payload.get("type") != "refresh":
            return None
        
        # Check expiration
        exp = payload.get("exp")
        if exp is None or datetime.utcnow().timestamp() > exp:
            return None
        
        return payload
    except Exception:
        return None