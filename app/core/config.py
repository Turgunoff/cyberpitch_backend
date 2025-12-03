# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import List
import secrets
import os
import logging

logger = logging.getLogger(__name__)


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

    # Email (Resend)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "noreply@cyberpitch.uz"

    # Push Notifications (OneSignal)
    ONESIGNAL_APP_ID: str = "5affee5f-1d19-460f-af51-af806e9b1c64"
    ONESIGNAL_REST_API_KEY: str = ""

    # Rasmlar
    UPLOAD_DIR: str = "uploads"
    AVATAR_DIR: str = "avatars"
    MAX_AVATAR_SIZE: int = 5 * 1024 * 1024  # 5MB
    AVATAR_QUALITY: int = 85  # JPEG sifati (1-100)
    AVATAR_SIZE: int = 400  # Kvadrat rasm o'lchami (400x400)
    BASE_URL: str = "https://nights.uz"  # Production server URL

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def validate_production(self) -> List[str]:
        """Production uchun muhim sozlamalarni tekshirish"""
        warnings = []
        errors = []

        # Critical checks
        if not self.DEBUG:
            if self.SECRET_KEY == secrets.token_urlsafe(32) or len(self.SECRET_KEY) < 32:
                errors.append("SECRET_KEY production uchun o'rnatilmagan!")

            if not self.RESEND_API_KEY:
                warnings.append("RESEND_API_KEY o'rnatilmagan - email yuborilmaydi")

            if not self.ONESIGNAL_REST_API_KEY:
                warnings.append("ONESIGNAL_REST_API_KEY o'rnatilmagan - push notification ishlamaydi")

            if "localhost" in self.DATABASE_URL:
                warnings.append("DATABASE_URL localhost ishlatmoqda")

        # Log warnings
        for warning in warnings:
            logger.warning(f"⚠️ CONFIG: {warning}")

        # Raise errors
        if errors:
            for error in errors:
                logger.error(f"❌ CONFIG: {error}")

        return errors


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()


settings = get_settings()


def validate_settings():
    """Startup da settings tekshirish"""
    errors = settings.validate_production()
    if errors and not settings.DEBUG:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
