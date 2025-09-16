from typing import Optional
import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

class WhatsAppClient:
    """
    Minimal async client mirroring the .NET SendWhatsAppMsg helper that hits 2whats.com.
    Env-driven configuration to avoid hardcoding secrets.
    """
    def __init__(self):
        self.enabled: bool = getattr(settings, "WHATSAPP_ENABLED", False)
        self.sender_mobile: Optional[str] = getattr(settings, "WHATSAPP_SENDER_MOBILE", None)
        self.instance_id: Optional[str] = getattr(settings, "WHATSAPP_INSTANCE_ID", None)
        self.password: Optional[str] = getattr(settings, "WHATSAPP_PASSWORD", None)
        self.base_url: str = "https://www.2whats.com/api/send"

    async def send(self, phone: str, body: str) -> dict:
        if not self.enabled:
            logger.info("WhatsApp sending disabled; skipping actual call.")
            return {"status": "disabled", "phone": phone, "message": body}

        if not (self.sender_mobile and self.instance_id and self.password):
            logger.error("WhatsApp configuration missing (sender_mobile/instance_id/password).")
            return {"status": "error", "error": "missing_configuration"}

        params = {
            "mobile": self.sender_mobile,     # mirrors .NET 'mobile' (sender)
            "password": self.password,
            "instanceid": self.instance_id,
            "message": body,
            "numbers": phone,
            "json": "1",
            "type": "1",
        }

        timeout = httpx.Timeout(10.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                r = await client.get(self.base_url, params=params)
                data = r.json() if r.headers.get("content-type","").startswith("application/json") else {"text": r.text}
                if r.is_success:
                    return {"status": "ok", "provider_response": data}
                else:
                    logger.error("WhatsApp send failed: %s | %s", r.status_code, data)
                    return {"status": "error", "code": r.status_code, "provider_response": data}
            except Exception as e:
                logger.exception("WhatsApp send exception: %s", e)
                return {"status": "error", "exception": str(e)}