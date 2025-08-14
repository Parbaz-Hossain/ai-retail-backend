from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.orm import relationship
from app.db.base import BaseModel

class Permission(BaseModel):
    __tablename__ = "permissions"

    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    resource = Column(String(100), nullable=False)  # e.g., 'inventory', 'hr', 'purchase'
    action = Column(String(50), nullable=False)     # e.g., 'read', 'write', 'delete'
    is_active = Column(Boolean, default=True)


    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Permission {self.name}>"