from typing import Optional, Generator
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.auth.jwt_handler import decode_access_token
from app.models.auth.user import User
from app.services.auth.user_service import UserService
from app.auth.permissions import PermissionChecker, get_permission_checker
from functools import wraps
import logging

security = HTTPBearer()
logger = logging.getLogger(__name__)

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_async_session)
) -> User:
    """Get current authenticated user"""
    try:
        # Decode token
        payload = decode_access_token(credentials.credentials)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user ID from token
        user_id = int(payload.get("sub"))
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user from database
        user_service = UserService(session)
        user = await user_service.get_user(user_id)
        
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Add request info to context
        request.state.current_user = user
        request.state.user_permissions = payload.get("permissions", [])
        
        return user
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current superuser"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

async def get_permission_checker_dependency(
    request: Request
) -> "PermissionChecker":
    """
    Get permission checker for current user from request state
    
    The permissions are already set in request.state by get_current_user
    """
    
    user_permissions = getattr(request.state, "user_permissions", [])
    current_user = getattr(request.state, "current_user", None)
    
    # Superusers have system:admin permission (full access)
    # if current_user and current_user.is_superuser:
    #     user_permissions = [{
    #         "name": "system:admin",
    #         "resource": "system",
    #         "action": "admin",
    #         "description": "Full system access"
    #     }]
    
    return PermissionChecker(user_permissions)

def require_permission(resource: str, action: str):
    """
    Dependency to require specific permission for an endpoint
        
    Examples:
        require_permission("user", "create")      # user:create
    """
    async def permission_dependency(
        request: Request,
        current_user = Depends(get_current_user)
    ):
        """Check if user has required permission"""
        try:
            # Get permission checker
            checker = await get_permission_checker_dependency(request)
            
            # Check permission
            checker.require(resource, action)
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Permission check error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission check failed: {str(e)}"
            )
    
    return permission_dependency

def require_any_permission(*permissions: tuple):
    """
    Require any one of the given permissions (OR logic)
    """
    async def permission_dependency(
        request: Request,
        current_user = Depends(get_current_user)
    ):
        checker = await get_permission_checker_dependency(request)
        
        # Try each permission
        if checker.has_any(*permissions):
            return True
        
        # None of the permissions matched
        perm_names = [f"{r}:{a}" for r, a in permissions]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required one of: {', '.join(perm_names)}"
        )
    
    return permission_dependency

def require_all_permissions(*permissions: tuple):
    """
    Require all given permissions (AND logic)
    """
    async def permission_dependency(
        request: Request,
        current_user = Depends(get_current_user)
    ):
        checker = await get_permission_checker_dependency(request)
        
        # Check all permissions
        if checker.has_all(*permissions):
            return True
        
        # Find which permissions are missing
        missing = []
        for resource, action in permissions:
            if checker.cannot(resource, action):
                missing.append(f"{resource}:{action}")
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Missing: {', '.join(missing)}"
        )
    
    return permission_dependency

def check_permission(resource: str, action: str):
    """
    Decorator to check permissions (alternative to Depends approach)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from kwargs
            request = kwargs.get("request")
            if not request:
                # Try to find request in args
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found"
                )
            
            # Get checker and verify permission
            checker = await get_permission_checker_dependency(request)
            checker.require(resource, action)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator