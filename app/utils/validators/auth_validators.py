from fastapi import HTTPException, status
import re

class AuthValidator:
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        return bool(re.match(email_regex, email))

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """
        Validate password strength.
        Must be at least 8 characters, include uppercase, lowercase, number, and special char.
        Returns (is_valid, message).
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r"\d", password):
            return False, "Password must contain at least one digit"
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False, "Password must contain at least one special character"
        return True, "Password is strong"

    @staticmethod
    def validate_username(username: str) -> bool:
        """
        Validate username format.
        Must be 3–20 characters, letters, numbers, underscores allowed.
        """
        username_regex = r"^[a-zA-Z0-9_]{3,20}$"
        return bool(re.match(username_regex, username))


def require_auth_validation(email: str = None, password: str = None, username: str = None):
    """Validation helper for registration/auth endpoints."""
    if email and not AuthValidator.validate_email(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )

    if password:
        is_valid, message = AuthValidator.validate_password_strength(password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )

    if username and not AuthValidator.validate_username(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username format. Only letters, numbers, and underscores are allowed (3–20 chars)."
        )
