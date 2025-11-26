# app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any


class EmailLoginRequest(BaseModel):
    """Email orqali kod yuborish"""
    email: EmailStr = Field(..., description="Foydalanuvchi email manzili")


class VerifyOTPRequest(BaseModel):
    """OTP kodni tekshirish"""
    email: EmailStr = Field(..., description="Email manzil")
    code: str = Field(..., min_length=6, max_length=6, description="6 xonali tasdiqlash kodi")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Qurilma ma'lumotlari")


class TokenResponse(BaseModel):
    """Token javob"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool = False
    expires_in: int = Field(..., description="Token muddati (soniyada)")


class RefreshTokenRequest(BaseModel):
    """Token yangilash"""
    refresh_token: str