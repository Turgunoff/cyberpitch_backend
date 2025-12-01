# app/main.py
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from app.api import auth, tournaments, users, upload, matches, home

import logging
import time

from app.core.config import settings
from app.core.database import init_db, check_db_connection

# Logging sozlash
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup va shutdown events"""
    # Startup
    logger.info("🚀 CyberPitch server ishga tushmoqda...")
    
    # Database connection check
    if check_db_connection():
        logger.info("✅ Database ulandi")
        # Jadvallarni yaratish (faqat mavjud bo'lmaganlarini)
        init_db()
        logger.info("✅ Jadvallar tayyor")
    else:
        logger.error("❌ Database ulanmadi!")
    
    yield
    
    # Shutdown
    logger.info("👋 Server yopilmoqda...")


app = FastAPI(
    title="CyberPitch API",
    description="Mobile Football League Backend - PES Tournament Platform",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,  # Production'da docs yopiq
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)


# CORS sozlamalari
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [
        "https://cyberpitch.uz",
        "https://app.cyberpitch.uz"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2)) + "ms"
    return response


# Validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"][1:])  # Skip "body"
        errors.append({
            "field": field,
            "message": error["msg"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors
        }
    )


# Generic error handler
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error: {exc}")
    
    if settings.DEBUG:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Ichki xatolik yuz berdi"}
    )

app.include_router(
    auth.router, 
    prefix="/api/v1/auth", 
    tags=["🔐 Authentication"]
)

app.include_router(
    tournaments.router, 
    prefix="/api/v1/tournaments", 
    tags=["🏆 Tournaments"]
)

# Router qo'shish (tournaments dan keyin)
app.include_router(
    users.router,
    prefix="/api/v1/users",
    tags=["👤 Users"]
)

app.include_router(
    upload.router,
    prefix="/api/v1/upload",
    tags=["📷 Upload"]
)

app.include_router(
    matches.router,
    prefix="/api/v1/matches",
    tags=["🎮 Matches"]
)

app.include_router(
    home.router,
    prefix="/api/v1/home",
    tags=["🏠 Home"]
)

# Health check endpoints
@app.get("/", tags=["Health"])
def root():
    """Root endpoint"""
    return {
        "status": "active",
        "message": "CyberPitch Server ishlamoqda! 🚀",
        "version": "1.0.0"
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check - load balancer uchun"""
    db_status = "connected" if check_db_connection() else "disconnected"
    
    return {
        "status": "healthy",
        "database": db_status,
        "debug_mode": settings.DEBUG
    }


@app.get("/api/v1", tags=["Health"])
def api_info():
    """API haqida ma'lumot"""
    return {
        "name": "CyberPitch API",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/api/v1/auth",
            "tournaments": "/api/v1/tournaments",
            "matches": "/api/v1/matches",
            "users": "/api/v1/users"
        }
    }
