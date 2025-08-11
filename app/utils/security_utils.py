import secrets
import string
import hashlib
import hmac
from typing import Optional
from datetime import datetime, timedelta
from app.core.config import settings

class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate cryptographically secure random token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate API key"""
        return f"ak_{''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(40))}"
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def verify_signature(payload: str, signature: str, secret: str) -> bool:
        """Verify HMAC signature"""
        expected_signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)
    
    @staticmethod
    def is_safe_url(url: str) -> bool:
        """Check if URL is safe for redirects"""
        allowed_domains = ['localhost', '127.0.0.1']
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            
            # Only allow relative URLs or whitelisted domains
            if not parsed.netloc:
                return True
            
            return parsed.netloc in allowed_domains
            
        except Exception:
            return False