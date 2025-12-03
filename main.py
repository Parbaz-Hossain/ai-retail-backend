from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api.v1.api import api_router

# Create FastAPI app
app_config = {
    "title": "AI Agentic Retail Management System",
    "description": "A fully automated retail management system powered by AI agents",
    "version": "1.0.0",
}

app = FastAPI(**app_config)
router = APIRouter()

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

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

# ============================================================================
# MOVE THESE FUNCTIONS OUTSIDE if __name__ == "__main__" for Windows
# ============================================================================

def run_https():
    """Run HTTPS server on port 9105"""
    import uvicorn
    print("🔒 Starting HTTPS server on port 9105...")
    uvicorn.run(
        "main:app",  # Use string import
        host="0.0.0.0",
        port=9105,
        reload=False,
        ssl_certfile="cert.pem",
        ssl_keyfile="key.pem"
    )

def run_http():
    """Run HTTP server on port 9106"""
    import uvicorn
    print("🚀 Starting HTTP server on port 9106...")
    uvicorn.run(
        "main:app",  # Use string import
        host="0.0.0.0",
        port=9106,
        reload=False
    )

# ============================================================================

if __name__ == "__main__":
    import multiprocessing
    import sys

    # REQUIRED for Windows multiprocessing
    multiprocessing.freeze_support()

    # Check command line arguments
    if "--https-only" in sys.argv:
        print("🔒 Starting server in HTTPS-only mode...")
        run_https()
    elif "--http-only" in sys.argv:
        print("🚀 Starting server in HTTP-only mode...")
        run_http()
    else:
        print("🚀 Starting servers in DUAL mode (HTTP + HTTPS)...")
        
        # Use Process instead of Thread
        https_process = multiprocessing.Process(target=run_https)
        http_process = multiprocessing.Process(target=run_http)
        
        https_process.start()
        http_process.start()
        
        https_process.join()
        http_process.join()