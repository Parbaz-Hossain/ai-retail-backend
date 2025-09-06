import logging
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.schemas.auth.user import UserCreate, UserUpdate, UserResponse
from app.schemas.common.pagination import PaginatedResponse
from app.services.auth.user_service import UserService
from app.api.dependencies import get_current_user, get_current_superuser

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=UserResponse)
async def create_user(
    user_create: UserCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """Create new user (admin only)"""
    try:
        user_service = UserService(session)
        
        new_user = await user_service.create_user(
            user_create=user_create,
            created_by=current_user.id
        )
        
        # Get user with roles
        roles = await user_service.get_user_roles(new_user.id)
            
        user_response = UserResponse.model_validate(new_user, from_attributes=True)
        user_response.roles = [
            {"id": role.id, "name": role.name, "description": role.description}
            for role in roles
        ]
        return user_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create user error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

@router.get("/", response_model=PaginatedResponse[UserResponse])
async def get_users(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: str = Query(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Get users list with pagination (admin only)"""
    try:
        user_service = UserService(session)
        
        result = await user_service.get_users(
            page_index=page_index,
            page_size=page_size,
            search=search
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Get users error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users"
        )
    
@router.get("/count")
async def get_users_count(
    search: str = Query(None),
    session: AsyncSession = Depends(get_async_session)
):
    """Get users count (admin only)"""
    try:
        user_service = UserService(session)
        count = await user_service.count_users(search=search)
        return {"count": count}
        
    except Exception as e:
        logger.error(f"Get users count error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users count"
        )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Get user by ID"""
    try:
        user_service = UserService(session)
        
        # Allow users to get their own info or require admin
        if user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        user = await user_service.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get user roles
        roles = await user_service.get_user_roles(user.id)
        
        return UserResponse(
            **user.__dict__,
            roles=[{"id": role.id, "name": role.name, "description": role.description} for role in roles]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user"
        )

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """Update user"""
    try:
        user_service = UserService(session)
        
        # Allow users to update their own info or require admin
        if user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        updated_user = await user_service.update_user(user_id, user_update)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get user roles
        roles = await user_service.get_user_roles(updated_user.id)
        
        return UserResponse(
            **updated_user.__dict__,
            roles=[{"id": role.id, "name": role.name, "description": role.description} for role in roles]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """Delete user (admin only)"""
    try:
        user_service = UserService(session)
        
        # Prevent deleting own account
        if user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        success = await user_service.delete_user(user_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {"message": "User deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete user error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )

@router.post("/{user_id}/assign-role")
async def assign_role_to_user(
    user_id: int,
    role_name: str,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """Assign role to user (admin only)"""
    try:
        user_service = UserService(session)
        
        success = await user_service.assign_role_to_user(
            user_id=user_id,
            role_name=role_name,
            assigned_by=current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to assign role"
            )
        
        return {"message": f"Role '{role_name}' assigned successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assign role error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign role"
        )

@router.delete("/{user_id}/remove-role")
async def remove_role_from_user(
    user_id: int,
    role_name: str,
    session: AsyncSession = Depends(get_async_session)
):
    """Remove role from user (admin only)"""
    try:
        user_service = UserService(session)
        
        success = await user_service.remove_role_from_user(user_id, role_name)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove role"
            )
        
        return {"message": f"Role '{role_name}' removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove role error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove role"
        )