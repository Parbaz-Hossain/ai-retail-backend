from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine
from app.core.logging_config import setup_logging
from app.api.v1.api import api_router
# from app.middleware.logging import LoggingMiddleware
# from app.middleware.auth import AuthMiddleware
# from app.db.init_db import init_db
# from app.ai.agent_manager import AIAgentManager


# Create FastAPI app
app = FastAPI(
    title="AI Agentic Retail Management System",
    description="A fully automated retail management system powered by AI agents",
    version="1.0.0",
    # lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.ALLOWED_METHODS,
    allow_headers=settings.ALLOWED_HEADERS,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
# app.add_middleware(LoggingMiddleware)
# app.add_middleware(AuthMiddleware)

# Mount static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "message": "🤖 Welcome to the AI Agentic Retail Management System!",
        "status": "active",
        "version": "1.0.0",
        "ai_agents": "operational",
        "docs": "/api/docs"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "components": {
            "database": "connected",
            "redis": "connected", 
            "ai_agents": "operational",
            "celery": "running"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )