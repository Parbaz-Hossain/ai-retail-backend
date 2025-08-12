from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel

class User(BaseModel):
    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    profile_image = Column(String(500), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)
    verification_token = Column(String(255), nullable=True)
    verification_expires = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user_roles = relationship(
        "UserRole",
        back_populates="user",
        foreign_keys="UserRole.user_id",
        cascade="all, delete-orphan",
        overlaps="assigned_by_user,roles_assigned"
    )
    roles_assigned = relationship(
        "UserRole",
        foreign_keys="UserRole.assigned_by",
        back_populates="assigned_by_user",
        viewonly=True,  # set False if you want to edit from this side
        overlaps="user_roles,assigned_by_user"
    )
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"