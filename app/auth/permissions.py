# app/auth/permissions.py
# UPDATED to match your permission seed data structure

from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)


class PermissionChecker:
    """
    Check user permissions from JWT token
    """
    
    def __init__(self, user_permissions: List[Dict[str, Any]]):
        """
        Initialize with user permissions from JWT token
        """
        self.permissions = user_permissions or []
        self._permission_map = {}
        
        # Build quick lookup map for performance
        for perm in self.permissions:
            resource = perm.get("resource")
            action = perm.get("action")
            if resource and action:
                key = f"{resource}:{action}"
                self._permission_map[key] = True
        
        logger.debug(f"PermissionChecker initialized with {len(self.permissions)} permissions")
    
    def can(self, resource: str, action: str) -> bool:
        """
        Check if user can perform action on resource
            
        Examples:
            can("user", "create")  # Check if can create users
        """
        # Check for exact permission
        permission_key = f"{resource}:{action}"
        if permission_key in self._permission_map:
            logger.debug(f"Permission granted: {permission_key}")
            return True
        
        # Check for admin permission on this resource
        admin_key = f"{resource}:admin"
        if admin_key in self._permission_map:
            logger.debug(f"Permission granted: {permission_key} (via {admin_key})")
            return True
        
        # Check for system admin (full access)
        if "system:admin" in self._permission_map:
            logger.debug(f"Permission granted: {permission_key} (via system:admin)")
            return True
        
        logger.debug(f"Permission denied: {permission_key}")
        return False
    
    def cannot(self, resource: str, action: str) -> bool:
        """
        Check if user cannot perform action on resource
        """
        return not self.can(resource, action)
    
    def require(
        self, 
        resource: str,
        action: str,
        custom_message: Optional[str] = None
    ):
        """
        Require permission or raise HTTPException        
        """
        if self.cannot(resource, action):
            message = custom_message or f"Insufficient permissions to {action} {resource}"
            logger.warning(f"Permission check failed: {message}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=message
            )
    
    def has_any(self, *permission_tuples) -> bool:
        """
        Check if user has any of the given permissions (OR logic)
        """
        for resource, action in permission_tuples:
            if self.can(resource, action):
                return True
        return False
    
    def has_all(self, *permission_tuples) -> bool:
        """
        Check if user has all of the given permissions (AND logic)
        """
        for resource, action in permission_tuples:
            if self.cannot(resource, action):
                return False
        return True
    
    def get_permissions_for_resource(self, resource: str) -> List[str]:
        """
        Get all actions the user can perform on a resource
        """
        actions = []
        for perm in self.permissions:
            if perm.get("resource") == resource:
                actions.append(perm.get("action"))
        return actions
    
    def has_permission(self, permission_name: str) -> bool:
        """
        Check if user has permission by full name
        """
        if ":" in permission_name:
            resource, action = permission_name.split(":", 1)
            return self.can(resource, action)
        return False
    
    def get_all_permissions(self) -> List[str]:
        """
        Get all permission names for this user
        """
        return [perm.get("name", "") for perm in self.permissions if perm.get("name")]


def get_permission_checker(user_permissions: List[Dict[str, Any]]) -> PermissionChecker:
    """
    Get permission checker for user
    """
    return PermissionChecker(user_permissions)


def parse_permission_name(permission_name: str) -> tuple:
    """
    Parse permission name into resource and action
    """
    if ":" not in permission_name:
        raise ValueError(f"Invalid permission format: {permission_name}. Expected 'resource:action'")
    
    parts = permission_name.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid permission format: {permission_name}. Expected 'resource:action'")
    
    return parts[0], parts[1]


def format_permission_name(resource: str, action: str) -> str:
    """
    Format permission as string
    """
    return f"{resource}:{action}"