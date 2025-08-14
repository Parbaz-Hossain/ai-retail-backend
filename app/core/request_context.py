from typing import Optional, Dict
from fastapi import Request

# Names you’ll read from headers (change to match your FE/GW)
HDR_REQUEST_ID = "X-Request-Id"
HDR_SESSION_ID = "X-Session-Id"

def get_request_context(request: Request) -> Dict[str, Optional[str]]:
    """
    Extracts endpoint, client IP, user-agent, request_id, session_id from the FastAPI Request.
    - request_id/session_id are read from headers but fall back to None.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    endpoint = f"{request.method} {request.url.path}"
    request_id = request.headers.get(HDR_REQUEST_ID)
    session_id = request.headers.get(HDR_SESSION_ID)
    return {
        "ip_address": ip_address,
        "user_agent": user_agent,
        "endpoint": endpoint,
        "request_id": request_id,
        "session_id": session_id,
    }
