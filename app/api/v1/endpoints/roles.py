import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.schemas.auth.role import RoleCreate, RoleUpdate, Role
from app.services.auth.role_service import RoleService
from app.api.dependencies import get_current_superuser

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=Role)
async def create_role(
    role_create: RoleCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """Create new role (admin only)"""
    try:
        role_service = RoleService(session)
        new_role = await role_service.create_role(role_create)
        return new_role
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create role error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create role"
        )

@router.get("/", response_model=List[Role])
async def get_roles(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """Get roles list (admin only)"""
    try:
        role_service = RoleService(session)
        roles = await role_service.get_roles(skip=skip, limit=limit)
        return roles
        
    except Exception as e:
        logger.error(f"Get roles error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get roles"
        )

@router.get("/{role_id}", response_model=Role)
async def get_role(
    role_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """Get role by ID (admin only)"""
    try:
        role_service = RoleService(session)
        role = await role_service.get_role(role_id)
        
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        
        return role
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get role error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get role"
        )

@router.put("/{role_id}", response_model=Role)
async def update_role(
    role_id: int,
    role_update: RoleUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """Update role (admin only)"""
    try:
        role_service = RoleService(session)
        updated_role = await role_service.update_role(role_id, role_update)
        
        if not updated_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        
        return updated_role
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update role error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update role"
        )

@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """Delete role (admin only)"""
    try:
        role_service = RoleService(session)
        success = await role_service.delete_role(role_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        
        return {"message": "Role deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete role error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete role"
        )

@router.post("/{role_id}/assign-permission")
async def assign_permission_to_role(
    role_id: int,
    permission_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """Assign permission to role (admin only)"""
    try:
        role_service = RoleService(session)
        success = await role_service.assign_permission_to_role(role_id, permission_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to assign permission"
            )
        
        return {"message": "Permission assigned successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assign permission error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign permission"
        )

@router.delete("/{role_id}/remove-permission")
async def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """Remove permission from role (admin only)"""
    try:
        role_service = RoleService(session)
        success = await role_service.remove_permission_from_role(role_id, permission_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove permission"
            )
        
        return {"message": "Permission removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove permission error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove permission"
        )