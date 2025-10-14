import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, and_, or_
from sqlalchemy.orm import selectinload
from app.models.auth.user import User
from app.models.auth.role import Role
from app.models.auth.permission import Permission
from app.models.auth.user_role import UserRole
from app.models.auth.role_permission import RolePermission
from app.core.security import get_password_hash, generate_password_reset_token
from app.schemas.auth.user import UserCreate, UserResponse, UserUpdate
from openpyxl import Workbook
from sqlalchemy import select
from datetime import datetime
from io import BytesIO
from app.models.auth.user import User

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        try:
            result = await self.session.execute(
                select(User).where(
                    User.id == user_id,
                    User.is_deleted == False
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {str(e)}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        try:
            result = await self.session.execute(
                select(User).where(
                    User.email == email,
                    User.is_deleted == False
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user by email: {str(e)}")
            return None
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        try:
            result = await self.session.execute(
                select(User).where(
                    User.username == username,
                    User.is_deleted == False
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user by username: {str(e)}")
            return None
    
    async def get_users_by_roles(self, role_names: list) -> list:
        """Get active users by role names"""

        result = await self.session.execute(
            select(User)
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
            .where(User.is_active == True)
        )
        all_users = result.scalars().all()

        # Filter users by roles
        filtered_users = []
        for user in all_users:
            user_role_names = [ur.role.name.upper() for ur in user.user_roles if ur.is_active]
            if any(role.upper() in user_role_names for role in role_names):
                filtered_users.append(user)

        return filtered_users
    
    async def get_role_names_by_user(self, user_id: int) -> List[str]:
        """Get all active role names assigned to a user."""
        try:
            result = await self.session.execute(
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(
                    UserRole.user_id == user_id,
                    Role.is_active == True,
                    Role.is_deleted == False,
                    UserRole.is_active == True
                )
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting roles for user {user_id}: {str(e)}")
            return []
    
    async def create_user(self, user_create: UserCreate, created_by: Optional[int] = None) -> User:
        """Create new user"""
        try:
            # Check if email already exists
            existing_user = await self.get_user_by_email(user_create.email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Check if username already exists
            existing_username = await self.get_user_by_username(user_create.username)
            if existing_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
            
            # Create user
            db_user = User(
                email=user_create.email,
                username=user_create.username,
                full_name=user_create.full_name,
                hashed_password=get_password_hash(user_create.password),
                phone=user_create.phone,
                address=user_create.address,
                is_verified=False  # Requires email verification
            )
            
            self.session.add(db_user)
            await self.session.flush()  # Get the ID
            
            # Assign default role (employee)
            await self.assign_role_to_user(db_user.id, "employee", created_by)
            
            logger.info(f"User created: {user_create.email}")

            return db_user
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error creating user"
            )
    
    async def update_user(self, user_id: int, user_update: UserUpdate) -> Optional[User]:
        """Update user"""
        try:
            user = await self.get_user(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Update fields
            update_data = user_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(user, field, value)
            
            user.updated_at = datetime.utcnow()
            await self.session.commit()
            
            logger.info(f"User updated: {user.email}")
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error updating user"
            )
    
    async def delete_user(self, user_id: int, deleted_by: int) -> bool:
        """Soft delete user"""
        try:
            user = await self.get_user(user_id)
            if not user:
                return False
            
            user.is_deleted = True
            user.is_active = False
            user.updated_at = datetime.utcnow()
            
            await self.session.commit()
            logger.info(f"User deleted: {user.email}")
            
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting user: {str(e)}")
            return False
    
    async def get_user_roles(self, user_id: int) -> List[Role]:
        """Get all roles for user"""
        try:
            result = await self.session.execute(
                select(Role)
                .join(UserRole)
                .where(
                    UserRole.user_id == user_id,
                    Role.is_active == True,
                    Role.is_deleted == False
                )
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting user roles: {str(e)}")
            return []
    
    async def get_user_permissions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all permissions for user through roles"""
        try:
            result = await self.session.execute(
                select(Permission)
                .join(RolePermission)
                .join(Role)
                .join(UserRole)
                .where(
                    UserRole.user_id == user_id,
                    Role.is_active == True,
                    Permission.is_active == True
                )
                .distinct()
            )
            
            permissions = result.scalars().all()
            return [
                {
                    "name": perm.name,
                    "resource": perm.resource,
                    "action": perm.action,
                    "description": perm.description
                }
                for perm in permissions
            ]
            
        except Exception as e:
            logger.error(f"Error getting user permissions: {str(e)}")
            return []
    
    async def assign_role_to_user(self, user_id: int, role_name: str, assigned_by: Optional[int] = None) -> bool:
        """Assign role to user"""
        try:
            # Get role by name
            result = await self.session.execute(
                select(Role).where(Role.name == role_name, Role.is_active == True)
            )
            role = result.scalar_one_or_none()
            
            if not role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role '{role_name}' not found"
                )
            
            # Check if user already has this role
            existing_result = await self.session.execute(
                select(UserRole).where(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role.id
                )
            )
            existing_user_role = existing_result.scalar_one_or_none()
            
            if existing_user_role:
                return True  # Already assigned
            
            # Create user role assignment
            user_role = UserRole(
                user_id=user_id,
                role_id=role.id,
                assigned_by=assigned_by,
                assigned_at=datetime.utcnow()
            )
            
            self.session.add(user_role)
            await self.session.commit()
            
            logger.info(f"Role '{role_name}' assigned to user {user_id}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error assigning role: {str(e)}")
            return False
    
    async def remove_role_from_user(self, user_id: int, role_name: str) -> bool:
        """Remove role from user"""
        try:
            # Get role by name
            result = await self.session.execute(
                select(Role).where(Role.name == role_name)
            )
            role = result.scalar_one_or_none()
            
            if not role:
                return False
            
            # Find and delete user role assignment
            result = await self.session.execute(
                select(UserRole).where(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role.id
                )
            )
            user_role = result.scalar_one_or_none()
            
            if user_role:
                await self.session.delete(user_role)
                await self.session.commit()
                logger.info(f"Role '{role_name}' removed from user {user_id}")
                return True
            
            return False
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error removing role: {str(e)}")
            return False
    
    async def get_users(
        self,
        page_index: int = 1,
        page_size: int = 100,
        search: str = None
    ) -> Dict[str, Any]:
        """Get paginated list of users with roles"""
        try:
            conditions = [User.is_deleted == False]
            
            if search:
                search_term = f"%{search}%"
                conditions.append(
                    or_(
                        User.email.ilike(search_term),
                        User.username.ilike(search_term),
                        User.full_name.ilike(search_term)
                    )
                )
            
            # Get total count
            total_count = await self.session.scalar(
                select(func.count(User.id)).where(*conditions)
            )
            
            # Calculate offset
            skip = (page_index - 1) * page_size
            
            # Get paginated data
            users = await self.session.scalars(
                select(User)
                .where(*conditions)
                .offset(skip)
                .limit(page_size)
            )
            
            # Get roles for each user and create UserResponse objects
            user_responses = []
            for user in users.all():
                roles = await self.get_user_roles(user.id)
                user_response = UserResponse(
                    **user.__dict__,
                    roles=[
                        {"id": role.id, "name": role.name, "description": role.description}
                        for role in roles
                    ]
                )
                user_responses.append(user_response)
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total_count or 0,
                "data": user_responses
            }
            
        except Exception as e:
            logger.error(f"Error getting users: {str(e)}")
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }
    
    async def count_users(self, search: str = None) -> int:
        """Count users"""
        try:
            from sqlalchemy import func
            
            query = select(func.count(User.id)).where(User.is_deleted == False)
            
            if search:
                query = query.where(
                    or_(
                        User.email.ilike(f"%{search}%"),
                        User.username.ilike(f"%{search}%"),
                        User.full_name.ilike(f"%{search}%")
                    )
                )
            
            result = await self.session.execute(query)
            return result.scalar()
            
        except Exception as e:
            logger.error(f"Error counting users: {str(e)}")
            return 0
    
    async def change_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        """Change user password"""
        try:
            user = await self.get_user(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Verify current password
            from app.core.security import verify_password
            if not verify_password(current_password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )
            
            # Update password
            user.hashed_password = get_password_hash(new_password)
            user.updated_at = datetime.utcnow()
            
            await self.session.commit()
            logger.info(f"Password changed for user: {user.email}")
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error changing password: {str(e)}")
            return False

                # ---------- Excel export helpers ----------
    
    # ----------------------- User Excel Export -----------------------
    @staticmethod
    def _write_users_sheet(ws, users):
        ws.append(["ID", "Email", "Username", "Full Name", "Phone", "Is Active", "Is Verified", "Created At"])
        for u in users:
            created = getattr(u, "created_at", None)
            ws.append([
                u.id,
                u.email,
                u.username,
                getattr(u, "full_name", None),
                getattr(u, "phone", None),
                bool(u.is_active),
                bool(getattr(u, "is_verified", False)),
                created.strftime("%Y-%m-%d %H:%M:%S") if created else None,
            ])

    async def export_users_excel(self, deleted: bool = False) -> tuple[BytesIO, str]:
        """
        Build an Excel workbook of either active or deleted users.
        Returns: (file_bytes, filename)
        """
        result = await self.session.execute(
            select(User).where(User.is_deleted == deleted)
        )
        users = result.scalars().all()

        wb = Workbook()
        ws = wb.active
        ws.title = "Deleted Users" if deleted else "Users"
        self._write_users_sheet(ws, users)

        file_bytes = BytesIO()
        wb.save(file_bytes)
        file_bytes.seek(0)

        status_tag = "deleted" if deleted else "active"
        filename = f"{status_tag}_users_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return file_bytes, filename