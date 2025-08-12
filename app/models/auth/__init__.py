# app/models/auth/__init__.py

# Import models in dependency order
from .permission import Permission
from .role import Role
from .user import User
from .refresh_token import RefreshToken
from .role_permission import RolePermission
from .user_role import UserRole

# Make sure all models are available
__all__ = [
    "Permission",
    "Role", 
    "User",
    "RefreshToken",
    "RolePermission", 
    "UserRole"
]