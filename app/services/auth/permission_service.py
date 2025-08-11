import logging
from typing import Optional, List
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.auth.permission import Permission
from app.schemas.auth.permission import PermissionCreate, PermissionUpdate

logger = logging.getLogger(__name__)

class PermissionService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_permission(self, permission_id: int) -> Optional[Permission]:
        """Get permission by ID"""
        try:
            result = await self.session.execute(
                select(Permission).where(
                    Permission.id == permission_id,
                    Permission.is_deleted == False
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting permission {permission_id}: {str(e)}")
            return None
    
    async def get_permission_by_name(self, name: str) -> Optional[Permission]:
        """Get permission by name"""
        try:
            result = await self.session.execute(
                select(Permission).where(
                    Permission.name == name,
                    Permission.is_deleted == False
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting permission by name: {str(e)}")
            return None
    
    async def create_permission(self, permission_create: PermissionCreate) -> Permission:
        """Create new permission"""
        try:
            # Check if permission name already exists
            existing_permission = await self.get_permission_by_name(permission_create.name)
            if existing_permission:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Permission name already exists"
                )
            
            db_permission = Permission(
                name=permission_create.name,
                description=permission_create.description,
                resource=permission_create.resource,
                action=permission_create.action
            )
            
            self.session.add(db_permission)
            await self.session.commit()
            
            logger.info(f"Permission created: {permission_create.name}")
            return db_permission
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating permission: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating permission"
            )
    
    async def get_permissions(self, skip: int = 0, limit: int = 100) -> List[Permission]:
        """Get paginated list of permissions"""
        try:
            result = await self.session.execute(
                select(Permission)
                .where(Permission.is_deleted == False)
                .offset(skip)
                .limit(limit)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting permissions: {str(e)}")
            return []