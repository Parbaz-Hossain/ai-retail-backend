import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.schemas.auth.login import LoginRequest, LoginResponse, PasswordResetRequest, ChangePasswordRequest
from app.schemas.auth.token import Token, RefreshTokenRequest
from app.schemas.auth.user import UserResponse
from app.services.auth.auth_service import AuthService
from app.services.auth.user_service import UserService
from app.api.dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """Authenticate user and return tokens"""
    try:
        auth_service = AuthService(session)
        
        # Get client info
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        # Authenticate user
        user = await auth_service.authenticate_user(
            email=login_data.email,
            password=login_data.password,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Create tokens
        tokens = await auth_service.create_tokens(
            user=user,
            device_info=login_data.device_info,
            ip_address=ip_address
        )
        
        # Get user with roles
        await session.refresh(user)

        user_service = UserService(session)
        user_roles = await user_service.get_user_roles(user.id)
        
        user_out = UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        phone=user.phone,
        address=user.address,
        is_active=user.is_active,
        is_verified=user.is_verified,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        roles=[{"id": r.id, "name": r.name, "description": r.description} for r in user_roles],
        )

        return LoginResponse(
            user=user_out,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=tokens["expires_in"],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    """OAuth2 compatible token endpoint"""
    try:
        auth_service = AuthService(session)
        
        user = await auth_service.authenticate_user(
            email=form_data.username,  # OAuth2 uses username field for email
            password=form_data.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        tokens = await auth_service.create_tokens(user=user)
        
        return Token(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=tokens["expires_in"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token creation failed"
        )

@router.post("/refresh", response_model=dict)
async def refresh_token(
    token_data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """Refresh access token"""
    try:
        auth_service = AuthService(session)
        
        new_token = await auth_service.refresh_access_token(token_data.refresh_token)
        
        return new_token
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@router.post("/logout")
async def logout(
    token_data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Logout user by revoking refresh token"""
    try:
        auth_service = AuthService(session)
        
        # Revoke the specific refresh token
        await auth_service.revoke_refresh_token(token_data.refresh_token)
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@router.post("/logout-all")
async def logout_all_sessions(
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Logout from all sessions by revoking all refresh tokens"""
    try:
        auth_service = AuthService(session)
        
        # Revoke all refresh tokens for user
        revoked_count = await auth_service.revoke_all_refresh_tokens(current_user.id)
        
        return {"message": f"Logged out from {revoked_count} sessions"}
        
    except Exception as e:
        logger.error(f"Logout all error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout from all sessions failed"
        )

@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Change user password"""
    try:
        # Validate passwords match
        if password_data.new_password != password_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New passwords do not match"
            )
        
        user_service = UserService(session)
        success = await user_service.change_password(
            user_id=current_user.id,
            current_password=password_data.current_password,
            new_password=password_data.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to change password"
            )
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )

@router.get("/me", response_model=Any)
async def get_current_user_info(
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get current user information"""
    try:
        user_service = UserService(session)

        # Get user roles and permissions
        roles = await user_service.get_user_roles(current_user.id)
        permissions = await user_service.get_user_permissions(current_user.id)

        return {
        "user": jsonable_encoder(current_user),
        "roles": jsonable_encoder(roles),
        "permissions": jsonable_encoder(permissions),
        }
    
    except Exception as e:
        logger.error(f"Get current user info error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get current user info"
        )