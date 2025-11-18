import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from app.models.auth.role import Role
from app.models.auth.permission import Permission
from app.models.auth.role_permission import RolePermission
from app.schemas.auth.role import RoleCreate, RoleUpdate

logger = logging.getLogger(__name__)

class RoleService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_role(self, role_id: int) -> Optional[Role]:
        """Get role by ID"""
        try:
            result = await self.session.execute(
                select(Role)
                .options(
                    selectinload(Role.role_permissions.and_(RolePermission.is_active == True))
                    .selectinload(RolePermission.permission)
                )
                .where(
                    Role.id == role_id,
                    Role.is_deleted == False
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting role {role_id}: {str(e)}")
            return None
    
    async def get_role_by_name(self, name: str) -> Optional[Role]:
        """Get role by name"""
        try:
            result = await self.session.execute(
                select(Role).where(
                    Role.name == name,
                    Role.is_deleted == False
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting role by name: {str(e)}")
            return None
    
    async def create_role(self, role_create: RoleCreate) -> Role:
        """Create new role"""
        try:
            # Check if role name already exists
            existing_role = await self.get_role_by_name(role_create.name)
            if existing_role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Role name already exists"
                )
            
            db_role = Role(
                name=role_create.name,
                description=role_create.description
            )
            
            self.session.add(db_role)
            await self.session.commit()
            await self.session.refresh(db_role, attribute_names=["role_permissions"])
            
            logger.info(f"Role created: {role_create.name}")
            return db_role
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating role: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating role"
            )
    
    async def update_role(self, role_id: int, role_update: RoleUpdate) -> Optional[Role]:
        """Update role"""
        try:
            role = await self.get_role(role_id)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Role not found"
                )
            
            # Check if name is being changed and if new name already exists
            if role_update.name and role_update.name != role.name:
                existing_role = await self.get_role_by_name(role_update.name)
                if existing_role:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Role name already exists"
                    )
            
            # Update fields
            update_data = role_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(role, field, value)
            
            role.updated_at = datetime.utcnow()
            await self.session.commit()
            
            logger.info(f"Role updated: {role.name}")
            return role
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating role: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error updating role"
            )
    
    async def delete_role(self, role_id: int) -> bool:
        """Soft delete role"""
        try:
            role = await self.get_role(role_id)
            if not role:
                return False
            
            if role.is_system_role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete system role"
                )
            
            role.is_deleted = True
            role.is_active = False
            role.updated_at = datetime.utcnow()
            
            await self.session.commit()
            logger.info(f"Role deleted: {role.name}")
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting role: {str(e)}")
            return False
    
    async def get_roles(
        self,
        page_index: int = 1,
        page_size: int = 100,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get paginated list of roles with permissions"""
        try:
            conditions = [Role.is_deleted == False]

            if search:
                search_term = f"%{search}%"
                conditions.append(Role.name.ilike(search_term))
            
            # Get total count
            total_count = await self.session.scalar(
                select(func.count(Role.id)).where(*conditions)
            )
            
            # Calculate offset
            skip = (page_index - 1) * page_size
            
            # Get paginated data
            roles = await self.session.scalars(
                select(Role)
                .options(
                    selectinload(Role.role_permissions.and_(RolePermission.is_active == True))
                    .selectinload(RolePermission.permission)
                )
                .where(*conditions)
                .offset(skip)
                .limit(page_size)
            )
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": roles.all()
            }
            
        except Exception as e:
            logger.error(f"Error getting roles: {str(e)}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }
    
    async def assign_permission_to_role(self, role_id: int, permission_id: int) -> bool:
        """Assign permission to role"""
        try:
            # Check if assignment already exists
            result = await self.session.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id == permission_id
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                return True  # Already assigned
            
            # Create assignment
            role_permission = RolePermission(
                role_id=role_id,
                permission_id=permission_id
            )
            
            self.session.add(role_permission)
            await self.session.commit()
            
            logger.info(f"Permission {permission_id} assigned to role {role_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error assigning permission to role: {str(e)}")
            return False
    
    async def remove_permission_from_role(self, role_id: int, permission_id: int) -> bool:
        """Remove permission from role"""
        try:
            result = await self.session.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id == permission_id
                )
            )
            role_permission = result.scalar_one_or_none()
            
            if role_permission:
                await self.session.delete(role_permission)
                await self.session.commit()
                logger.info(f"Permission {permission_id} removed from role {role_id}")
                return True
            
            return False
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error removing permission from role: {str(e)}")
            return False
    
    async def get_role_permissions(self, role_id: int) -> List[Permission]:
        """Get all permissions for role"""
        try:
            result = await self.session.execute(
                select(Permission)
                .join(RolePermission)
                .where(
                    RolePermission.role_id == role_id,
                    Permission.is_active == True
                )
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting role permissions: {str(e)}")
            return []
        
    # Bulk permisson assignment/removal methods
    async def assign_multiple_permissions_to_role(
        self, 
        role_id: int, 
        permission_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Assign multiple permissions to role at once
        
        Args:
            role_id: ID of the role
            permission_ids: List of permission IDs to assign
            
        Returns:
            Dict with success status and counts
        """
        try:
            # Verify role exists
            role = await self.get_role(role_id)
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Role not found"
                )
            
            # Get existing permission assignments
            result = await self.session.execute(
                select(RolePermission.permission_id).where(
                    RolePermission.role_id == role_id
                )
            )
            existing_permission_ids = set(result.scalars().all())
            
            # Filter out already assigned permissions
            new_permission_ids = [
                pid for pid in permission_ids 
                if pid not in existing_permission_ids
            ]
            
            if not new_permission_ids:
                return {
                    "success": True,
                    "assigned_count": 0,
                    "skipped_count": len(permission_ids),
                    "invalid_count": 0,
                    "message": "All permissions were already assigned"
                }
            
            # Verify all new permissions exist and are active
            perm_result = await self.session.execute(
                select(Permission.id).where(
                    Permission.id.in_(new_permission_ids),
                    Permission.is_active == True,
                    Permission.is_deleted == False
                )
            )
            valid_permission_ids = set(perm_result.scalars().all())
            
            invalid_count = len(new_permission_ids) - len(valid_permission_ids)
            
            # Create bulk assignments
            role_permissions = [
                RolePermission(role_id=role_id, permission_id=pid)
                for pid in valid_permission_ids
            ]
            
            self.session.add_all(role_permissions)
            await self.session.commit()
            
            logger.info(
                f"{len(valid_permission_ids)} permissions assigned to role {role_id}"
            )
            
            return {
                "success": True,
                "assigned_count": len(valid_permission_ids),
                "skipped_count": len(existing_permission_ids & set(permission_ids)),
                "invalid_count": invalid_count,
                "message": f"Successfully assigned {len(valid_permission_ids)} permissions"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error assigning multiple permissions: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error assigning permissions"
            )

    async def remove_multiple_permissions_from_role(
        self,
        role_id: int,
        permission_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Remove multiple permissions from role at once
        
        Args:
            role_id: ID of the role
            permission_ids: List of permission IDs to remove
            
        Returns:
            Dict with success status and count
        """
        try:
            result = await self.session.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id.in_(permission_ids)
                )
            )
            role_permissions = result.scalars().all()
            
            if not role_permissions:
                return {
                    "success": True,
                    "removed_count": 0,
                    "message": "No matching permissions found to remove"
                }
            
            # Delete all found assignments
            for rp in role_permissions:
                await self.session.delete(rp)
            
            await self.session.commit()
            
            removed_count = len(role_permissions)
            logger.info(f"{removed_count} permissions removed from role {role_id}")
            
            return {
                "success": True,
                "removed_count": removed_count,
                "message": f"Successfully removed {removed_count} permissions"
            }
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error removing multiple permissions: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error removing permissions"
            )

    async def get_unassigned_permissions(self, role_id: int) -> List[Permission]:
        """
        Get permissions that are NOT assigned to this role (for dropdown)
        
        Args:
            role_id: ID of the role
            
        Returns:
            List of Permission objects not assigned to the role
        """
        try:
            # Get all assigned permission IDs for this role
            assigned_result = await self.session.execute(
                select(RolePermission.permission_id).where(
                    RolePermission.role_id == role_id
                )
            )
            assigned_ids = set(assigned_result.scalars().all())
            
            # Get all active permissions NOT in the assigned list
            if assigned_ids:
                result = await self.session.execute(
                    select(Permission).where(
                        Permission.is_active == True,
                        Permission.is_deleted == False,
                        ~Permission.id.in_(assigned_ids)
                    ).order_by(Permission.resource, Permission.action)
                )
            else:
                result = await self.session.execute(
                    select(Permission).where(
                        Permission.is_active == True,
                        Permission.is_deleted == False
                    ).order_by(Permission.resource, Permission.action)
                )
            
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting unassigned permissions: {str(e)}")
            return []

    async def get_assigned_permissions(self, role_id: int) -> List[Permission]:
        """
        Get permissions that ARE assigned to this role
        
        Args:
            role_id: ID of the role
            
        Returns:
            List of Permission objects assigned to the role
        """
        try:
            result = await self.session.execute(
                select(Permission)
                .join(RolePermission)
                .where(
                    RolePermission.role_id == role_id,
                    Permission.is_active == True,
                    Permission.is_deleted == False
                )
                .order_by(Permission.resource, Permission.action)
            )
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting assigned permissions: {str(e)}")
            return []