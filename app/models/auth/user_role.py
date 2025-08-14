from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class UserRole(BaseModel):
    __tablename__ = "user_roles"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship(
        "User",
        back_populates="user_roles",
        foreign_keys=[user_id],
        overlaps="roles_assigned,assigned_by_user"
    )
    role = relationship(
        "Role",
        back_populates="user_roles",
        foreign_keys=[role_id]
    )
    assigned_by_user = relationship(
        "User",
        foreign_keys=[assigned_by],
        back_populates="roles_assigned",
        overlaps="user_roles"
    )


    def __repr__(self):
        return f"<UserRole user_id={self.user_id} role_id={self.role_id}>"