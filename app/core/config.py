from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:pgadmin123@localhost/ai_retail_db"
    DATABASE_TEST_URL: str
    # DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost/ai_agentic_db" #ESAP SERVER

    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY")
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # JWT
    SECRET_KEY: str = "Y8lXe0iD5vdO2uNwIu5JoX_2nUYZhLRkjA_q7kKJcW0"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 540
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080
    
    # CORS
    ALLOWED_ORIGINS: List[AnyHttpUrl] = []
    ALLOWED_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    ALLOWED_HEADERS: List[str] = ["*"]
    
    # SMTP Email Settings   
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_USERNAME: Optional[str] = "parbazasit123@gmail.com"
    MAIL_PASSWORD: Optional[str] = "hexe nhbp tiqz qjeo"
    MAIL_FROM: Optional[str] = "parbazasit123@gmail.com"
    MAIL_FROM_NAME: Optional[str] = "AI Retail Management"
    
    # WhatsApp
    WHATSAPP_API_URL: str
    WHATSAPP_API_KEY: str
    
    # File Upload
    MAX_FILE_SIZE: int = 10485760  # 10MB
    UPLOAD_PATH: str = "./uploads"
    ALLOWED_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "pdf", "xlsx", "csv"]
    
    # AI Configuration
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-4"
    MAX_AI_RESPONSE_LENGTH: int = 2000
    AI_TEMPERATURE: float = 0.7
    
    # System
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = "Asia/Dhaka"
    
    # Security
    BCRYPT_ROUNDS: int = 12
    SESSION_EXPIRE_HOURS: int = 24
    
    # Business Rules
    MIN_REORDER_DAYS: int = 7
    MAX_TRANSFER_DAYS: int = 30
    SALARY_GENERATION_FROM_DAY: int = 25
    LATE_GRACE_MINUTES: int = 15
    OVERTIME_RATE_MULTIPLIER: float = 1.5

    @validator("ALLOWED_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()