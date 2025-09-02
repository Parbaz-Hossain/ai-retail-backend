import logging
from typing import Optional, List
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
    
    async def get_roles(self, skip: int = 0, limit: int = 100) -> List[Role]:
        """Get paginated list of roles"""
        try:
            result = await self.session.execute(
                select(Role)
                .where(Role.is_deleted == False)
                .offset(skip)
                .limit(limit)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting roles: {str(e)}")
            return []
    
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