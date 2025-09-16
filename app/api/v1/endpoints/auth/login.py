# app/routers/login.py  (merged classic + OTP flows)
import logging
import random
import time
from typing import Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
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
from app.services.communication.email_service import EmailService
from app.utils.rate_limiter import check_login_rate_limit
from app.core.config import settings
from app.services.communication.whatsapp_service import WhatsAppClient

router = APIRouter()
logger = logging.getLogger(__name__)

# ==============================
# OTP / Cookie configuration
# ==============================
OTP_COOKIE_NAME = getattr(settings, "OTP_COOKIE_NAME", "otpData")
OTP_COOKIE_TTL_MINUTES = int(getattr(settings, "OTP_COOKIE_TTL_MINUTES", 300))
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

def _make_timestamp() -> int:
    """Generate consistent Unix timestamp"""
    return int(time.time())

def _encode_cookie(payload: dict) -> str:
    """Use consistent timestamp generation"""
    current_time = _make_timestamp()
    exp_time = current_time + (OTP_COOKIE_TTL_MINUTES * 60)
    
    data = {
        **payload, 
        "exp": exp_time,
        "iat": current_time
    }
    
    logger.info(f"Creating JWT with iat={current_time}, exp={exp_time}, ttl={OTP_COOKIE_TTL_MINUTES} minutes")
    
    return jwt.encode(data, OTP_COOKIE_SECRET, algorithm="HS256")

def _decode_cookie(token: str) -> Optional[dict]:
    """Decode with detailed logging"""
    try:
        current_time = _make_timestamp()
        logger.info(f"Attempting to decode JWT at timestamp: {current_time}")
        
        decoded = jwt.decode(token, OTP_COOKIE_SECRET, algorithms=["HS256"])
        logger.info(f"JWT decoded successfully at {current_time}")
        return decoded
        
    except jwt.ExpiredSignatureError:
        current_time = _make_timestamp()
        logger.error(f"JWT expired at timestamp: {current_time}")
        return {"error": "expired"}
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT: {e}")
        return {"error": "invalid"}
    except Exception as e:
        logger.error(f"JWT decode error: {e}")
        return {"error": "decode_failed"}
    
def _set_cookie(resp: Response, name: str, value: str, ttl_minutes: int):
    """Set cookie with proper configuration"""
    resp.set_cookie(
        key=name,
        value=value,
        max_age=ttl_minutes * 60,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
    )

def _clear_cookie(resp: Response, name: str):
    """Clear cookie - Fixed FastAPI signature"""
    resp.delete_cookie(key=name, path="/")
    # Also clear with domain if set (for cross-subdomain cookies)
    if COOKIE_DOMAIN:
        resp.delete_cookie(key=name, path="/", domain=COOKIE_DOMAIN)

async def _send_otp(email: str, phone: Optional[str], code: str):
    if email:
        email_service = EmailService()
        
        #region Modern OTP email template
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Your OTP Code</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1); overflow: hidden;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 600;">Verification Code</h1>
                <p style="color: #e8f0fe; margin: 8px 0 0 0; font-size: 16px;">Secure access to your account</p>
            </div>
            
            <!-- Content -->
            <div style="padding: 40px 30px;">
                <div style="text-align: center; margin-bottom: 30px;">
                <p style="font-size: 18px; color: #333333; margin: 0 0 20px 0; line-height: 1.4;">
                    Hi there! 👋
                </p>
                <p style="font-size: 16px; color: #666666; margin: 0 0 30px 0; line-height: 1.6;">
                    Use this verification code to complete your login or password reset:
                </p>
                
                <!-- OTP Code Box -->
                <div style="background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); border: 2px solid #e2e8f0; border-radius: 12px; padding: 25px; margin: 30px 0; display: inline-block;">
                    <div style="font-size: 36px; font-weight: 700; color: #1a202c; letter-spacing: 8px; font-family: 'Courier New', monospace;">
                    {code}
                    </div>
                </div>
                
                <div style="background-color: #fff8e1; border-left: 4px solid #ffc107; padding: 15px; margin: 25px 0; border-radius: 4px;">
                    <p style="margin: 0; font-size: 14px; color: #8b6914;">
                    <strong>⏰ This code expires in {OTP_COOKIE_TTL_MINUTES} minutes</strong>
                    </p>
                </div>
                </div>
                
                <!-- Security Notice -->
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 25px 0;">
                <p style="margin: 0 0 10px 0; font-size: 14px; color: #495057; font-weight: 600;">
                    🔐 Security Notice:
                </p>
                <ul style="margin: 0; padding-left: 20px; font-size: 14px; color: #6c757d; line-height: 1.5;">
                    <li>Never share this code with anyone</li>
                    <li>We'll never ask for your code via phone or email</li>
                    <li>If you didn't request this, please ignore this email</li>
                </ul>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="background-color: #f8f9fa; padding: 25px 30px; text-align: center; border-top: 1px solid #e9ecef;">
                <p style="margin: 0; font-size: 14px; color: #6c757d;">
                Best regards,<br>
                <strong>The Support Team</strong>
                </p>
                <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e9ecef;">
                <p style="margin: 0; font-size: 12px; color: #adb5bd;">
                    This is an automated message. Please do not reply to this email.
                </p>
                </div>
            </div>
            </div>
            
            <!-- Footer outside card -->
            <div style="text-align: center; padding: 20px;">
            <p style="margin: 0; font-size: 12px; color: #adb5bd;">
                © {datetime.utcnow().year} ESAP AI. All rights reserved.
            </p>
            </div>
        </body>
        </html>
        """
        
        # Clean text version
        text_content = f"""
        VERIFICATION CODE
        
        Hi there!
        
        Use this verification code to complete your login or password reset:
        
        {code}
        
        ⏰ This code expires in {OTP_COOKIE_TTL_MINUTES} minutes
        
        SECURITY NOTICE:
        • Never share this code with anyone
        • We'll never ask for your code via phone or email
        • If you didn't request this, please ignore this email
        
        Best regards,
        The Support Team
        
        ---
        This is an automated message. Please do not reply to this email.
        """
        #endregion

        await email_service.send_email(
            to_email=email,
            subject="🔐 Your verification code",
            html_content=html_content,
            text_content=text_content
        )
        logger.info("Sending OTP %s to email %s", code, email)

    # WhatsApp OTP notification
    if phone:
        client = WhatsAppClient()
        msg = f"🔐 Your verification code: {code}\n\n⏰ Valid for {OTP_COOKIE_TTL_MINUTES} minutes\n\nNever share this code with anyone."
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
        
        """Step 1: Verify credentials then send OTP via email/WhatsApp and set httpOnly cookie 'otpData'."""
        try:
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
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in login OTP init: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initiate OTP login"
            )

@router.post("/login-otp-check", status_code=200)
async def login_otp_check(
    request: Request,
    response: Response,
    data: OtpInput,
    session: AsyncSession = Depends(get_async_session),
):
    """Step 2: Verify OTP from cookie, create auth tokens, set auth cookies, clear OTP cookie."""
    try:
        # Debug: Log all cookies
        logger.info(f"All cookies received: {dict(request.cookies)}")
        logger.info(f"Looking for cookie: {OTP_COOKIE_NAME}")
        
        # Get and decode cookie
        cookie = request.cookies.get(OTP_COOKIE_NAME)
        logger.info(f"OTP cookie found: {bool(cookie)}")
        
        if not cookie:
            logger.warning("No OTP cookie found in request")
            raise HTTPException(status_code=400, detail="OTP session not found")
        
        logger.info(f"Cookie value (first 20 chars): {cookie[:20]}...")
        
        try:
            payload = _decode_cookie(cookie)
            logger.info(f"Payload decoded successfully: {bool(payload)}")
            if payload:
                logger.info(f"Payload purpose: {payload.get('purpose')}")
                logger.info(f"Payload user_id: {payload.get('user_id')}")
                logger.info(f"Payload exp: {payload.get('exp')}")
        except Exception as e:
            logger.error(f"Failed to decode OTP cookie: {e}")
            logger.error(f"Cookie content: {cookie}")
            raise HTTPException(status_code=400, detail="Invalid OTP session")
        
        # Validate payload
        if not payload:
            logger.error("Payload is None after decoding")
            raise HTTPException(status_code=400, detail="OTP session not found or expired.")
            
        if payload.get("purpose") != "login":
            logger.error(f"Wrong purpose: {payload.get('purpose')} (expected: login)")
            raise HTTPException(status_code=400, detail="OTP session not found or expired.")
        
        # Check expiration manually
        exp_timestamp = payload.get("exp")
        current_timestamp = int(_now().timestamp())
        logger.info(f"Token exp: {exp_timestamp}, Current: {current_timestamp}")
        
        if exp_timestamp and current_timestamp > exp_timestamp:
            logger.error("Token has expired")
            raise HTTPException(status_code=400, detail="OTP session expired.")
        
        if payload.get("otp") != data.otp:
            logger.error(f"OTP mismatch. Expected: {payload.get('otp')}, Got: {data.otp}")
            raise HTTPException(status_code=400, detail="Invalid OTP.")

        # Get user ID safely
        try:
            user_id = int(payload["user_id"])
            logger.info(f"User ID: {user_id}")
        except (ValueError, KeyError, TypeError) as e:
            logger.error(f"Invalid user_id in payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid OTP session")

        # Get user
        user_svc = UserService(session)
        user = await user_svc.get_user(user_id)
        if not user or not user.is_active:
            logger.error(f"User not found or inactive: {user_id}")
            raise HTTPException(status_code=401, detail="User not found or inactive.")

        logger.info("Creating tokens...")
        
        # Create tokens
        auth = AuthService(session)
        req_ctx = get_request_context(request)
        tokens = await auth.create_tokens(
            user=user, 
            device_info="", 
            ip_address=req_ctx["ip_address"]
        )

        logger.info("Tokens created successfully")

        # Clear OTP cookie and set auth cookies
        _clear_cookie(response, OTP_COOKIE_NAME)
        
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

        logger.info("Login OTP check completed successfully")
        return {"message": "Login successful.", **tokens}
        
    except HTTPException:
        raise  
    except Exception as e:
        logger.error(f"Error checking OTP: {e}", exc_info=True)  
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check OTP"
        )
      
@router.post("/login-otp-resend", status_code=200)
async def login_otp_resend(
    request: Request,
    response: Response,
):
        
        """Resend login OTP with a cooldown."""
        try: 
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
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error resending OTP: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to resend OTP"
            )

@router.post("/forgot-password-init", status_code=200)
async def forgot_password_init(
    data: ForgotInitInput,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
):
        
        """Start password reset: sets 'otpData' cookie with purpose=reset and sends OTP."""
        try:
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
            return {"message": "Password reset OTP sent to your email/WhatsApp (if configured).", "expires_in_minutes": OTP_COOKIE_TTL_MINUTES}
        
        except Exception as e:
            logger.error(f"Error in forgot password init: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initiate password reset"
            )

@router.post("/forgot-password-check", status_code=200)
async def forgot_password_check(
    request: Request,
    response: Response,
    data: OtpInput,
):
        """Verify OTP for reset then allow /reset-password-otp."""
        try:
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
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking forgot password OTP: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify password reset OTP"
            )

@router.post("/reset-password-otp", status_code=200)
async def reset_password_otp(
    request: Request,
    response: Response,
    data: ResetInput,
    session: AsyncSession = Depends(get_async_session),
):
        """Finalize password reset using verified OTP cookie."""
        try:
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
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error resetting password: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset password"
            )