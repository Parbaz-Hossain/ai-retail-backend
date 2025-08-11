from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.base import BaseModel

class Role(BaseModel):
    __tablename__ = "roles"

    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    is_system_role = Column(Boolean, default=False)

    # Relationships
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    role_permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Role {self.name}>"