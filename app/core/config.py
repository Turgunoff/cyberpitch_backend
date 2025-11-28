# app/core/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache
import secrets
import os


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://cyber_admin:cyber_parol_2025@localhost/cyberpitch_db"

    # Security - MUHIM: Production'da .env dan o'qiladi
    SECRET_KEY: str = secrets.token_urlsafe(32)  # Default random key
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 soat
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OTP
    OTP_EXPIRATION_SECONDS: int = 120  # 2 daqiqa
    OTP_MAX_ATTEMPTS: int = 5  # Maksimum urinishlar
    OTP_BLOCK_MINUTES: int = 15  # Block vaqti

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # soniyada

    # App
    APP_NAME: str = "CyberPitch"
    DEBUG: bool = False

    # Rasmlar
    UPLOAD_DIR: str = "uploads"
    AVATAR_DIR: str = "avatars"
    MAX_AVATAR_SIZE: int = 5 * 1024 * 1024  # 5MB
    AVATAR_QUALITY: int = 85  # JPEG sifati (1-100)
    AVATAR_SIZE: int = 400  # Kvadrat rasm o'lchami (400x400)
    BASE_URL: str = "https://nights.uz"  # Production server URL

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()


settings = get_settings()
