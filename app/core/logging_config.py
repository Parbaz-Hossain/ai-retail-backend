import logging
import logging.config
import os
from datetime import datetime
from app.core.config import settings

def setup_logging():
    """Setup application logging configuration"""
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    os.makedirs("logs/app", exist_ok=True)
    os.makedirs("logs/access", exist_ok=True)
    os.makedirs("logs/error", exist_ok=True)
    os.makedirs("logs/celery", exist_ok=True)
    os.makedirs("logs/ai", exist_ok=True)
    
    # Get current date for log file naming
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "access": {
                "format": "%(asctime)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "detailed",
                "filename": f"logs/app/app-{current_date}.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": f"logs/error/error-{current_date}.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
            },
            "access_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "access",
                "filename": f"logs/access/access-{current_date}.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
            },
            "ai_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "detailed",
                "filename": f"logs/ai/ai-{current_date}.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
            },
            "celery_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "detailed",
                "filename": f"logs/celery/celery-{current_date}.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
            },
        },
        "loggers": {
            "": {  # Root logger
                "level": settings.LOG_LEVEL,
                "handlers": ["console", "app_file", "error_file"],
                "propagate": False,
            },
            "app.ai": {
                "level": "INFO",
                "handlers": ["ai_file", "console"],
                "propagate": False,
            },
            "celery": {
                "level": "INFO",
                "handlers": ["celery_file", "console"],
                "propagate": False,
            },
            "access": {
                "level": "INFO",
                "handlers": ["access_file"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["access_file"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING",  # Reduce DB query noise
                "handlers": ["app_file"],
                "propagate": False,
            },
        },
    }
    
    logging.config.dictConfig(logging_config)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("🚀 AI Agentic Retail Management System - Logging configured")
    logger.info(f"📝 Log level: {settings.LOG_LEVEL}")
    logger.info(f"🗂️  Logs directory: ./logs/")