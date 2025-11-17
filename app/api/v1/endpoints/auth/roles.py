import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_async_session
from app.schemas.auth.role import RoleCreate, RoleUpdate, Role
from app.schemas.auth.permission import PermissionResponse
from app.schemas.common.pagination import PaginatedResponse
from app.services.auth.permission_service import PermissionService
from app.services.auth.role_service import RoleService
from app.api.dependencies import get_current_superuser, get_current_user, require_permission

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# PYDANTIC SCHEMAS for Bulk Operations
# ============================================================================

class BulkPermissionAssignment(BaseModel):
    """Schema for assigning multiple permissions to a role"""
    permission_ids: List[int] = Field(
        ..., 
        min_items=1,
        description="List of permission IDs to assign"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "permission_ids": [1, 2, 3, 4, 5]
            }
        }

class BulkPermissionRemoval(BaseModel):
    """Schema for removing multiple permissions from a role"""
    permission_ids: List[int] = Field(
        ..., 
        min_items=1,
        description="List of permission IDs to remove"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "permission_ids": [1, 2, 3]
            }
        }

# ============================================================================
# ROLE CRUD ENDPOINTS
# ============================================================================

@router.post("/", response_model=Role)
async def create_role(
    request: Request,
    role_create: RoleCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """
    Create new role (admin only)
    """
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

@router.get("/", response_model=PaginatedResponse[Role])
async def get_roles(
    request: Request,
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: str = Query(None),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """
    Get roles list with pagination (admin only)
    """
    try:
        role_service = RoleService(session)
        result = await role_service.get_roles(
            page_index=page_index,
            page_size=page_size,
            search=search
        )
        return result
        
    except Exception as e:
        logger.error(f"Get roles error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get roles"
        )

@router.get("/all-permissions", response_model=PaginatedResponse[PermissionResponse])
async def get_permissions(
    request: Request,
    page_index: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    resource: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search in name and description"),
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """
    Get paginated list of permissions (admin only)
    """
    try:
        permission_service = PermissionService(session)
        permissions = await permission_service.get_permissions(
            page_index=page_index,
            page_size=page_size,
            resource=resource,
            action=action,
            is_active=is_active,
            search=search
        )
        return permissions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get permissions error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get permissions"
        )

@router.get("/{role_id}", response_model=Role)
async def get_role(
    request: Request,
    role_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """
    Get role by ID (admin only)
    """
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
    request: Request,
    role_id: int,
    role_update: RoleUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """
    Update role (admin only)
    """
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
    request: Request,
    role_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """
    Delete role (admin only)
    """
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

# ============================================================================
# SINGLE PERMISSION ASSIGNMENT (Original)
# ============================================================================

@router.post("/{role_id}/assign-permission")
async def assign_permission_to_role(
    request: Request,
    role_id: int,
    permission_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """
    Assign single permission to role (admin only)
    """
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
    request: Request,
    role_id: int,
    permission_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """
    Remove single permission from role (admin only)
    """
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

# ============================================================================
# BULK PERMISSION ASSIGNMENT (NEW)
# ============================================================================

@router.post("/{role_id}/assign-permissions", response_model=dict)
async def assign_multiple_permissions_to_role(
    request: Request,
    role_id: int,
    assignment: BulkPermissionAssignment,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """
    Assign multiple permissions to a role at once (admin only)

    Request body example:
    {
        "permission_ids": [1, 2, 3, 4, 5]
    }
    
    """
    try:
        if not assignment.permission_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No permission IDs provided"
            )
        
        role_service = RoleService(session)
        result = await role_service.assign_multiple_permissions_to_role(
            role_id, 
            assignment.permission_ids
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assign multiple permissions error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign permissions"
        )

@router.delete("/{role_id}/remove-permissions", response_model=dict)
async def remove_multiple_permissions_from_role(
    request: Request,
    role_id: int,
    removal: BulkPermissionRemoval,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_superuser)
):
    """
    Remove multiple permissions from a role at once (admin only)
    
    Request body example:
    {
        "permission_ids": [1, 2, 3]
    }
    """
    try:
        if not removal.permission_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No permission IDs provided"
            )
        
        role_service = RoleService(session)
        result = await role_service.remove_multiple_permissions_from_role(
            role_id,
            removal.permission_ids
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove multiple permissions error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove permissions"
        )

# ============================================================================
# PERMISSION LISTING FOR DROPDOWNS
# ============================================================================

@router.get("/{role_id}/unassigned-permissions", response_model=List[PermissionResponse])
async def get_unassigned_permissions_for_role(
    request: Request,
    role_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Get list of permissions NOT assigned to this role (for dropdown selection)
    """
    try:
        role_service = RoleService(session)
        
        # Verify role exists
        role = await role_service.get_role(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        
        permissions = await role_service.get_unassigned_permissions(role_id)
        return permissions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get unassigned permissions error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get unassigned permissions"
        )

@router.get("/{role_id}/assigned-permissions", response_model=List[PermissionResponse])
async def get_assigned_permissions_for_role(
    request: Request,
    role_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Get list of permissions assigned to this role
    """
    try:
        role_service = RoleService(session)
        
        # Verify role exists
        role = await role_service.get_role(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )
        
        permissions = await role_service.get_assigned_permissions(role_id)
        return permissions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get assigned permissions error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get assigned permissions"
        )