# app/core/config.py
import os
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings loaded from .env"""

    # === Database ===
    DATABASE_URL: str
    DATABASE_TEST_URL: Optional[str] = None

    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Ensure database URL is safe for current environment"""
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env == "production" and "localhost" in v:
            raise ValueError("🚨 Production environment cannot use localhost database!")
        return v

    # === External APIs ===
    GOOGLE_MAPS_API_KEY: Optional[str] = None

    # === Redis / Celery ===
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # === JWT ===
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_MINUTES: int

    # === CORS ===
    ALLOWED_ORIGINS: List[str] = ["http://localhost:8083","http://127.0.0.1:8083","http://localhost:8081","http://127.0.0.1:8081"]
    ALLOWED_METHODS: List[str] = ["*"]
    ALLOWED_HEADERS: List[str] = ["*"]

    # === SMTP (Email) ===
    MAIL_SERVER: Optional[str] = None
    MAIL_PORT: Optional[int] = None
    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[str] = None
    MAIL_FROM: Optional[str] = None
    MAIL_FROM_NAME: Optional[str] = None
    MAIL_TLS: bool = True
    MAIL_SSL: bool = False

    # === WhatsApp ===
    WHATSAPP_API_URL: Optional[str] = None
    WHATSAPP_API_KEY: Optional[str] = None

    # === File Upload ===
    MAX_FILE_SIZE: Optional[int] = None
    UPLOAD_PATH: Optional[str] = None
    ALLOWED_EXTENSIONS: List[str] = []

    # === AI ===
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    AI_MODEL: Optional[str] = None
    MAX_AI_RESPONSE_LENGTH: Optional[int] = None
    AI_TEMPERATURE: Optional[float] = None

    # === System ===
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = "Asia/Dhaka"

    # === Security ===
    BCRYPT_ROUNDS: int = 12
    SESSION_EXPIRE_HOURS: int = 24

    # === Business Rules ===
    MIN_REORDER_DAYS: int = 7
    MAX_TRANSFER_DAYS: int = 30
    SALARY_GENERATION_FROM_DAY: int = 25
    LATE_GRACE_MINUTES: int = 15
    OVERTIME_RATE_MULTIPLIER: float = 1.5


    OTP_COOKIE_SECRET: str = "change-me"
    OTP_COOKIE_NAME: str = "otpData"
    OTP_COOKIE_TTL_MINUTES: int = 300
    OTP_RESEND_COOLDOWN_SECONDS: int = 60

    ACCESS_TOKEN_COOKIE: str = "access_token"
    REFRESH_TOKEN_COOKIE: str = "refresh_token"
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"   # 'lax' | 'strict' | 'none'
    COOKIE_DOMAIN: Optional[str] = None      # or your domain

    WHATSAPP_ENABLED: bool = True
    WHATSAPP_SENDER_MOBILE: str = "966538748591"
    WHATSAPP_INSTANCE_ID: str = "234909"
    WHATSAPP_PASSWORD: str = "Ee@@19801980"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Create a global settings instance
settings = Settings()