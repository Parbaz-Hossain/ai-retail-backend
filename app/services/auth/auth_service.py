import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.auth.user import User
from app.models.auth.refresh_token import RefreshToken
from app.models.auth.audit_log import AuditLog
from app.core.security import verify_password, create_access_token, create_refresh_token
from app.core.config import settings
from app.services.auth.user_service import UserService

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(session)
    
    async def authenticate_user(
        self, 
        email: str, 
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        endpoint: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[User]:
        """Authenticate user with email and password"""
        try:
            # Get user by email
            result = await self.session.execute(
                select(User).where(User.email == email, User.is_active == True)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await self._log_failed_login(email, "User not found", ip_address, user_agent)
                return None
            
            # Check if account is locked
            if user.locked_until and user.locked_until > datetime.utcnow():
                await self._log_failed_login(email, "Account locked", ip_address, user_agent)
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account is locked due to too many failed attempts"
                )
            
            # Verify password
            if not verify_password(password, user.hashed_password):
                await self._handle_failed_login(user, ip_address, user_agent)
                return None
            
            # Reset failed attempts on successful login
            if user.failed_login_attempts > 0:
                user.failed_login_attempts = 0
                user.locked_until = None
            
            # Update last login
            user.last_login = datetime.utcnow()
            await self.session.commit()
            
            # Log successful login
            await self._log_audit(
                user_id=user.id,
                action="login",
                resource="auth",
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint = endpoint,
                request_id = request_id,
                session_id = session_id
            )
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error authenticating user: {str(e)}")
            return None
    
    async def create_tokens(
        self, 
        user: User,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create access and refresh tokens for user"""
        try:
            # Get user permissions
            permissions = await self.user_service.get_user_permissions(user.id)
            
            # Create access token
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={
                    "sub": str(user.id),
                    "email": user.email,
                    "username": user.username,
                    "is_superuser": user.is_superuser,
                    "permissions": permissions
                },
                expires_delta=access_token_expires
            )
            
            # Create refresh token
            refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
            refresh_token = create_refresh_token(
                data={"sub": str(user.id)},
                expires_delta=refresh_token_expires
            )
            
            # Store refresh token in database
            db_refresh_token = RefreshToken(
                user_id=user.id,
                token=refresh_token,
                expires_at=datetime.utcnow() + refresh_token_expires,
                device_info=device_info,
                ip_address=ip_address
            )
            self.session.add(db_refresh_token)
            await self.session.commit()
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
            
        except Exception as e:
            logger.error(f"Error creating tokens: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating authentication tokens"
            )
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            from app.auth.jwt_handler import decode_refresh_token
            
            # Decode refresh token
            payload = decode_refresh_token(refresh_token)
            if not payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired refresh token"
                )
            
            user_id = int(payload.get("sub"))
            
            # Check if refresh token exists in database and is not revoked
            result = await self.session.execute(
                select(RefreshToken).where(
                    RefreshToken.token == refresh_token,
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False,
                    RefreshToken.expires_at > datetime.utcnow()
                )
            )
            db_token = result.scalar_one_or_none()
            
            if not db_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token not found or revoked"
                )
            
            # Get user
            user = await self.user_service.get_user(user_id)
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive"
                )
            
            # Create new access token
            permissions = await self.user_service.get_user_permissions(user.id)
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={
                    "sub": str(user.id),
                    "email": user.email,
                    "username": user.username,
                    "is_superuser": user.is_superuser,
                    "permissions": permissions
                },
                expires_delta=access_token_expires
            )
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error refreshing token"
            )
    
    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke refresh token"""
        try:
            result = await self.session.execute(
                select(RefreshToken).where(RefreshToken.token == refresh_token)
            )
            db_token = result.scalar_one_or_none()
            
            if db_token:
                db_token.is_revoked = True
                await self.session.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error revoking token: {str(e)}")
            return False
    
    async def revoke_all_refresh_tokens(self, user_id: int) -> int:
        """Revoke all refresh tokens for user"""
        try:
            result = await self.session.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False
                )
            )
            tokens = result.scalars().all()
            
            revoked_count = 0
            for token in tokens:
                token.is_revoked = True
                revoked_count += 1
            
            await self.session.commit()
            return revoked_count
            
        except Exception as e:
            logger.error(f"Error revoking all tokens: {str(e)}")
            return 0
    
    async def _handle_failed_login(
        self, 
        user: User, 
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Handle failed login attempt"""
        user.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(hours=1)
            logger.warning(f"Account locked for user {user.email}")
        
        await self.session.commit()
        
        await self._log_failed_login(user.email, "Invalid password", ip_address, user_agent)
    
    async def _log_failed_login(
        self,
        email: str,
        reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        endpoint: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """Log failed login attempt"""
        await self._log_audit(
            action="login_failed",
            resource="auth",
            details={"email": email, "reason": reason},
            ip_address=ip_address,
            user_agent=user_agent,
            endpoint = endpoint,
            request_id = request_id,
            session_id = session_id
        )
    
    async def _log_audit(
        self,
        action: str,
        resource: str,
        user_id: Optional[int] = None,
        resource_id: Optional[int] = None,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        endpoint: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """Log audit event"""
        try:
            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                resource=resource,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint = endpoint,
                request_id = request_id,
                session_id = session_id
            )
            self.session.add(audit_log)
            await self.session.commit()
        except Exception as e:
            logger.error(f"Error logging audit event: {str(e)}")