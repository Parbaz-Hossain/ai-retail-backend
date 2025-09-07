import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.schemas.auth.user import UserCreate, UserResponse
from app.services.auth.user_service import UserService
from app.services.communication.email_service import EmailService
from app.utils.rate_limiter import check_login_rate_limit
from app.utils.validators.auth_validators import require_auth_validation

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/register", response_model=UserResponse)
async def register_user(
    request: Request,
    user_create: UserCreate,
    session: AsyncSession = Depends(get_async_session),
     _: None = Depends(check_login_rate_limit)
):
    """Register new user with email verification"""
    try:
        # Validate input
        require_auth_validation(
            email=user_create.email,
            password=user_create.password,
            username=user_create.username
        )
        
        user_service = UserService(session)
        email_service = EmailService()
        
        # Create user
        new_user = await user_service.create_user(user_create)
        
        # Send welcome email (async)
        await email_service.send_welcome_email(
            to_email=new_user.email,
            username=new_user.username
        )
        
        # Get user with roles
        roles = await user_service.get_user_roles(new_user.id)
        
        logger.info(f"New user registered: {new_user.email}")
        
        user_response = UserResponse.model_validate(new_user, from_attributes=True)
        user_response.roles = [
            {"id": role.id, "name": role.name, "description": role.description}
            for role in roles
        ]
        return user_response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )