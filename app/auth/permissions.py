from typing import List, Dict, Any
from enum import Enum
from fastapi import HTTPException, status

class Resource(str, Enum):
    INVENTORY = "inventory"
    HR = "hr"
    PURCHASE = "purchase"
    LOGISTICS = "logistics"
    REPORTS = "reports"
    USERS = "users"
    ROLES = "roles"
    SYSTEM = "system"

class Action(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"

class PermissionChecker:
    """Check user permissions using CASL-like approach"""
    
    def __init__(self, user_permissions: List[Dict[str, Any]]):
        self.permissions = user_permissions
    
    def can(self, action: Action, resource: Resource, resource_id: int = None) -> bool:
        """Check if user can perform action on resource"""
        for permission in self.permissions:
            if (permission.get("action") == action.value or permission.get("action") == Action.ADMIN.value) and \
               (permission.get("resource") == resource.value or permission.get("resource") == "all"):
                return True
        return False
    
    def cannot(self, action: Action, resource: Resource, resource_id: int = None) -> bool:
        """Check if user cannot perform action on resource"""
        return not self.can(action, resource, resource_id)
    
    def require(self, action: Action, resource: Resource, resource_id: int = None):
        """Require permission or raise HTTPException"""
        if self.cannot(action, resource, resource_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions to {action.value} {resource.value}"
            )

def get_permission_checker(user_permissions: List[Dict[str, Any]]) -> PermissionChecker:
    """Get permission checker for user"""
    return PermissionChecker(user_permissions)