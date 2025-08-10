# import logging
# from fastapi import Request, HTTPException, status
# from fastapi.security import HTTPBearer
# from starlette.middleware.base import BaseHTTPMiddleware
# # from app.auth.jwt_handler import decode_access_token

# logger = logging.getLogger(__name__)
# security = HTTPBearer()

# class AuthMiddleware(BaseHTTPMiddleware):
#     """Middleware for authentication"""
    
#     # Routes that don't require authentication
#     EXEMPT_ROUTES = [
#         "/",
#         "/health",
#         "/api/docs",
#         "/api/redoc",
#         "/api/openapi.json",
#         "/api/v1/auth/login",
#         "/api/v1/auth/register",
#         "/uploads",
#     ]
    
#     async def dispatch(self, request: Request, call_next):
#         # Check if route is exempt from authentication
#         if any(request.url.path.startswith(route) for route in self.EXEMPT_ROUTES):
#             return await call_next(request)
        
#         # Get authorization header
#         authorization = request.headers.get("Authorization")
        
#         if not authorization:
#             # For development, allow requests without auth on non-critical endpoints
#             if request.url.path.startswith("/api/v1/dashboard") and request.app.state.get("debug"):
#                 return await call_next(request)
            
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Authorization header required"
#             )
        
#         try:
#             # Extract token from "Bearer <token>"
#             scheme, token = authorization.split()
#             if scheme.lower() != "bearer":
#                 raise HTTPException(
#                     status_code=status.HTTP_401_UNAUTHORIZED,
#                     detail="Invalid authentication scheme"
#                 )
            
#             # Decode and validate token
#             # payload = decode_access_token(token)
#             if payload is None:
#                 raise HTTPException(
#                     status_code=status.HTTP_401_UNAUTHORIZED,
#                     detail="Invalid or expired token"
#                 )
            
#             # Add user info to request state
#             request.state.user = payload
            
#         except ValueError:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Invalid authorization header format"
#             )
#         except Exception as e:
#             logger.error(f"Authentication error: {str(e)}")
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Authentication failed"
#             )
        
#         return await call_next(request)
















