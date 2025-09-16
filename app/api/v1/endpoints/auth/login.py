# app/routers/login.py  (merged classic + OTP flows)
import logging
import random
from typing import Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

# Make sure these imports match your project structure
from app.core.database import get_async_session
from app.core.request_context import get_request_context
from app.api.dependencies import get_current_user
from app.schemas.auth.login import LoginRequest, LoginResponse, ChangePasswordRequest, OtpInput, ForgotInitInput, ResetInput
from app.schemas.auth.token import Token, RefreshTokenRequest
from app.schemas.auth.user import UserResponse
from app.services.auth.auth_service import AuthService
from app.services.auth.user_service import UserService
from app.utils.rate_limiter import check_login_rate_limit
from app.core.config import settings
from app.helper.whatsapp_service import WhatsAppClient

router = APIRouter()
logger = logging.getLogger(__name__)

# ==============================
# OTP / Cookie configuration
# ==============================
OTP_COOKIE_NAME = getattr(settings, "OTP_COOKIE_NAME", "otpData")
OTP_COOKIE_TTL_MINUTES = int(getattr(settings, "OTP_COOKIE_TTL_MINUTES", 5))
OTP_RESEND_COOLDOWN_SECONDS = int(getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60))
OTP_COOKIE_SECRET = getattr(settings, "OTP_COOKIE_SECRET", getattr(settings, "SECRET_KEY", "change-me"))
ACCESS_TOKEN_COOKIE = getattr(settings, "ACCESS_TOKEN_COOKIE", "access_token")
REFRESH_TOKEN_COOKIE = getattr(settings, "REFRESH_TOKEN_COOKIE", "refresh_token")
COOKIE_SECURE = bool(getattr(settings, "COOKIE_SECURE", True))
COOKIE_DOMAIN = getattr(settings, "COOKIE_DOMAIN", None)
COOKIE_SAMESITE = getattr(settings, "COOKIE_SAMESITE", "lax").lower()

def _now() -> datetime:
    return datetime.utcnow()

def _make_otp() -> str:
    return f"{random.randint(1000, 9999)}"

def _encode_cookie(payload: dict) -> str:
    exp = int(payload.get("exp", (_now() + timedelta(minutes=OTP_COOKIE_TTL_MINUTES)).timestamp()))
    data = {**payload, "exp": exp, "iat": int(_now().timestamp())}
    return jwt.encode(data, OTP_COOKIE_SECRET, algorithm="HS256")

def _decode_cookie(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, OTP_COOKIE_SECRET, algorithms=["HS256"])
    except JWTError:
        return None

def _set_cookie(resp: Response, name: str, value: str, ttl_minutes: int):
    resp.set_cookie(
        key=name,
        value=value,
        max_age=ttl_minutes * 60,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
    )

def _clear_cookie(resp: Response, name: str):
    resp.delete_cookie(name=name, domain=COOKIE_DOMAIN)

async def _send_otp(email: str, phone: Optional[str], code: str):
    # Email stub — replace with your real mailer if available
    logger.info("Sending OTP %s to email %s", code, email)
    # WhatsApp
    if phone:
        client = WhatsAppClient()
        msg = f"Your verification code is: {code}"
        await client.send(phone, msg)

# ==============================
# Classic login + tokens (kept)
# ==============================
@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(check_login_rate_limit),
):
    """Authenticate user and return tokens (non-OTP path kept for backward compatibility)."""
    try:
        auth_service = AuthService(session)
        req_context = get_request_context(request)

        user = await auth_service.authenticate_user(
            email=login_data.email,
            password=login_data.password,
            ip_address=req_context["ip_address"],
            user_agent=req_context["user_agent"],
            endpoint=req_context["endpoint"],
            request_id=req_context["request_id"],
            session_id=req_context["session_id"],
        )
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

        tokens = await auth_service.create_tokens(
            user=user,
            device_info="",
            ip_address=req_context["ip_address"],
        )

        await session.refresh(user)
        user_service = UserService(session)
        user_roles = await user_service.get_user_roles(user.id)

        user_out = UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            phone=user.phone,
            address=user.address,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login,
            roles=[{"id": r.id, "name": r.name, "description": r.description} for r in user_roles],
        )

        return LoginResponse(
            user=user_out,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=tokens["expires_in"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session),
):
    """OAuth2 compatible token endpoint."""
    try:
        auth_service = AuthService(session)
        user = await auth_service.authenticate_user(email=form_data.username, password=form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        tokens = await auth_service.create_tokens(user=user)
        return Token(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=tokens["expires_in"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token creation failed")

@router.post("/refresh", response_model=dict)
async def refresh_token(
    token_data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Refresh access token."""
    try:
        auth_service = AuthService(session)
        new_token = await auth_service.refresh_access_token(token_data.refresh_token)
        return new_token
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token refresh failed")

@router.post("/logout")
async def logout(
    token_data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    """Logout user by revoking refresh token."""
    try:
        auth_service = AuthService(session)
        await auth_service.revoke_refresh_token(token_data.refresh_token)
        return {"message": "Successfully logged out"}
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed")

@router.post("/logout")
async def logout(
    token_data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    """Logout user by revoking refresh token."""
    try:
        auth_service = AuthService(session)
        await auth_service.revoke_refresh_token(token_data.refresh_token)
        return {"message": "Successfully logged out"}
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed")

@router.post("/logout-all")
async def logout_all_sessions(
    session: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    """Logout from all sessions by revoking all refresh tokens."""
    try:
        auth_service = AuthService(session)
        revoked_count = await auth_service.revoke_all_refresh_tokens(current_user.id)
        return {"message": f"Logged out from {revoked_count} sessions"}
    except Exception as e:
        logger.error(f"Logout all error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout from all sessions failed")

@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    """Change user password (requires current password)."""
    try:
        if password_data.new_password != password_data.confirm_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New passwords do not match")

        user_service = UserService(session)
        success = await user_service.change_password(
            user_id=current_user.id,
            current_password=password_data.current_password,
            new_password=password_data.new_password,
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to change password")

        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Password change failed")

@router.get("/me", response_model=Any)
async def get_current_user_info(
    session: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
):
    """Get current user information."""
    try:
        user_service = UserService(session)
        roles = await user_service.get_user_roles(current_user.id)
        permissions = await user_service.get_user_permissions(current_user.id)
        return {
            "user": jsonable_encoder(current_user),
            "roles": jsonable_encoder(roles),
            "permissions": jsonable_encoder(permissions),
        }
    except Exception as e:
        logger.error(f"Get current user info error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get current user info")

# ==============================
# NEW: OTP login + password reset endpoints
# ==============================

@router.post("/login-otp-init", status_code=200)
async def login_otp_init(
    request: Request,
    data: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    _: None = Depends(check_login_rate_limit),
):
        try:
            """Step 1: Verify credentials then send OTP via email/WhatsApp and set httpOnly cookie 'otpData'."""
            auth = AuthService(session)
            req_ctx = get_request_context(request)

            user = await auth.authenticate_user(
                email=data.email,
                password=data.password,
                ip_address=req_ctx["ip_address"],
                user_agent=req_ctx["user_agent"],
                endpoint=req_ctx["endpoint"],
                request_id=req_ctx["request_id"],
                session_id=req_ctx["session_id"],
            )
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

            code = _make_otp()
            payload = {
                "purpose": "login",
                "user_id": user.id,
                "email": user.email,
                "phone": user.phone,
                "otp": code,
                "last_sent": int(_now().timestamp()),
                "exp": int((_now() + timedelta(minutes=OTP_COOKIE_TTL_MINUTES)).timestamp()),
            }
            token = _encode_cookie(payload)
            _set_cookie(response, OTP_COOKIE_NAME, token, OTP_COOKIE_TTL_MINUTES)

            await _send_otp(user.email, user.phone, code)
            return {"message": "OTP sent to your email/WhatsApp (if configured).", "expires_in_minutes": OTP_COOKIE_TTL_MINUTES}
        
        except Exception as e:
                logger.error(f"Error exporting users: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to login"
                )


@router.post("/login-otp-check", status_code=200)
async def login_otp_check(
    request: Request,
    response: Response,
    data: OtpInput,
    session: AsyncSession = Depends(get_async_session),
):
        try:
            """Step 2: Verify OTP from cookie then mint tokens. Also sets auth cookies for parity with Node UX."""
            cookie = request.cookies.get(OTP_COOKIE_NAME)
            payload = _decode_cookie(cookie) if cookie else None
            if not payload or payload.get("purpose") != "login":
                raise HTTPException(status_code=400, detail="OTP session not found or expired.")
            if payload.get("otp") != data.otp:
                raise HTTPException(status_code=400, detail="Invalid OTP.")

            user_svc = UserService(session)
            user = await user_svc.get_user(int(payload["user_id"]))
            if not user or not user.is_active:
                raise HTTPException(status_code=401, detail="User not found or inactive.")

            auth = AuthService(session)
            req_ctx = get_request_context(request)
            tokens = await auth.create_tokens(user=user, device_info="", ip_address=req_ctx["ip_address"])

            _clear_cookie(response, OTP_COOKIE_NAME)

            # Optional cookie delivery for SPA parity (keep if your frontend expects cookies)
            response.set_cookie(
                key=ACCESS_TOKEN_COOKIE,
                value=tokens["access_token"],
                httponly=True,
                secure=COOKIE_SECURE,
                samesite=COOKIE_SAMESITE,
                domain=COOKIE_DOMAIN,
                max_age=int(tokens["expires_in"]),
            )
            response.set_cookie(
                key=REFRESH_TOKEN_COOKIE,
                value=tokens["refresh_token"],
                httponly=True,
                secure=COOKIE_SECURE,
                samesite=COOKIE_SAMESITE,
                domain=COOKIE_DOMAIN,
                max_age=int(getattr(settings, "REFRESH_TOKEN_EXPIRE_MINUTES", 10080)) * 60,
            )

            return {"message": "Login successful.", **tokens}
        except Exception as e:
            logger.error(f"Error exporting users: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to check OTP"
            )


@router.post("/login-otp-resend", status_code=200)
async def login_otp_resend(
    request: Request,
    response: Response,
):
        try: 
            """Resend login OTP with a cooldown."""
            cookie = request.cookies.get(OTP_COOKIE_NAME)
            payload = _decode_cookie(cookie) if cookie else None
            if not payload or payload.get("purpose") != "login":
                raise HTTPException(status_code=400, detail="No active OTP session.")

            last_sent = int(payload.get("last_sent", 0))
            now = int(_now().timestamp())
            if now - last_sent < OTP_RESEND_COOLDOWN_SECONDS:
                raise HTTPException(status_code=429, detail="Please wait before requesting another code.")

            code = _make_otp()
            payload["otp"] = code
            payload["last_sent"] = now

            token = _encode_cookie(payload)
            _set_cookie(response, OTP_COOKIE_NAME, token, OTP_COOKIE_TTL_MINUTES)

            await _send_otp(payload.get("email"), payload.get("phone"), code)
            return {"message": "OTP resent."}
        except Exception as e:
            logger.error(f"Error exporting users: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to Resend OTP"
            )

@router.post("/forgot-password-init", status_code=200)
async def forgot_password_init(
    data: ForgotInitInput,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
):
        try:
            """Start password reset: sets 'otpData' cookie with purpose=reset and sends OTP."""
            user_svc = UserService(session)
            user = await user_svc.get_user_by_email(data.email)
            if not user:
                # Do not reveal user existence
                return {"message": "If the account exists, we sent a code."}

            code = _make_otp()
            payload = {
                "purpose": "reset",
                "user_id": user.id,
                "email": user.email,
                "phone": user.phone,
                "otp": code,
                "last_sent": int(_now().timestamp()),
                "exp": int((_now() + timedelta(minutes=OTP_COOKIE_TTL_MINUTES)).timestamp()),
            }
            token = _encode_cookie(payload)
            _set_cookie(response, OTP_COOKIE_NAME, token, OTP_COOKIE_TTL_MINUTES)

            await _send_otp(user.email, user.phone, code)
            return {"message": "If the account exists, we sent a code."}
        except Exception as e:
            logger.error(f"Error exporting users: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to Forget Password"
            )

@router.post("/forgot-password-check", status_code=200)
async def forgot_password_check(
    request: Request,
    response: Response,
    data: OtpInput,
):
        try:
            """Verify OTP for reset then allow /reset-password-otp."""
            cookie = request.cookies.get(OTP_COOKIE_NAME)
            payload = _decode_cookie(cookie) if cookie else None
            if not payload or payload.get("purpose") != "reset":
                raise HTTPException(status_code=400, detail="OTP session not found or expired.")
            if payload.get("otp") != data.otp:
                raise HTTPException(status_code=400, detail="Invalid OTP.")

            payload["purpose"] = "reset_verified"
            token = _encode_cookie(payload)
            _set_cookie(response, OTP_COOKIE_NAME, token, OTP_COOKIE_TTL_MINUTES)
            return {"message": "OTP verified. You may now reset your password."}
        except Exception as e:
            logger.error(f"Error exporting users: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to check password OTP"
            )

@router.post("/reset-password-otp", status_code=200)
async def reset_password_otp(
    request: Request,
    response: Response,
    data: ResetInput,
    session: AsyncSession = Depends(get_async_session),
):
        try:
            """Finalize password reset using verified OTP cookie."""
            cookie = request.cookies.get(OTP_COOKIE_NAME)
            payload = _decode_cookie(cookie) if cookie else None
            if not payload or payload.get("purpose") != "reset_verified":
                raise HTTPException(status_code=400, detail="Reset not authorized or expired.")

            user_id = int(payload["user_id"])
            user_svc = UserService(session)
            user = await user_svc.get_user(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found.")

            from app.core.security import get_password_hash
            user.hashed_password = get_password_hash(data.new_password)
            user.updated_at = datetime.utcnow()
            await session.commit()

            _clear_cookie(response, OTP_COOKIE_NAME)
            return {"message": "Password has been reset successfully."}
        except Exception as e:
            logger.error(f"Error exporting users: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to check OTP"
            )