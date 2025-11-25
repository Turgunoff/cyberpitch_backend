# app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import random

from app.core.database import get_db
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.users import User, Profile
from app.schemas.auth import (
    EmailLoginRequest, 
    VerifyOTPRequest, 
    TokenResponse,
    RefreshTokenRequest
)
from app.services.otp_service import (
    generate_and_save_otp, 
    verify_otp_in_redis,
    is_blocked,
    get_remaining_attempts
)

router = APIRouter()


@router.post("/send-code", summary="Tasdiqlash kodini yuborish")
def send_code(request: EmailLoginRequest):
    """
    Email manziliga 6 xonali tasdiqlash kodini yuboradi.
    Dev mode'da kod terminalga chiqariladi.
    """
    # Bloklangan bo'lsa
    blocked, remaining = is_blocked(request.email)
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Juda ko'p urinish. {remaining} soniyadan keyin qayta urinib ko'ring."
        )
    
    try:
        generate_and_save_otp(request.email)
        return {
            "message": "Tasdiqlash kodi yuborildi",
            "expires_in": settings.OTP_EXPIRATION_SECONDS
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Kod yuborishda xatolik yuz berdi"
        )


@router.post("/verify-code", response_model=TokenResponse, summary="Kodni tekshirish va kirish")
def verify_code(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    """
    OTP kodni tekshiradi va JWT tokenlarni qaytaradi.
    Yangi foydalanuvchi bo'lsa avtomatik ro'yxatdan o'tkazadi.
    """
    # Bloklangan bo'lsa
    blocked, remaining = is_blocked(request.email)
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Juda ko'p urinish. {remaining} soniyadan keyin qayta urinib ko'ring."
        )
    
    try:
        if not verify_otp_in_redis(request.email, request.code):
            remaining_attempts = get_remaining_attempts(request.email)
            detail = "Kod noto'g'ri yoki eskirgan"
            if remaining_attempts > 0:
                detail += f". Qolgan urinishlar: {remaining_attempts}"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e)
        )

    # Userni qidirish yoki yaratish
    user = db.query(User).filter(User.email == request.email).first()
    is_new_user = False

    if not user:
        is_new_user = True
        user = User(email=request.email)
        db.add(user)
        db.flush()  # ID olish uchun

        # Nickname yaratish
        base_nickname = request.email.split("@")[0]
        nickname = base_nickname
        
        # Agar band bo'lsa, raqam qo'shish
        counter = 1
        while db.query(Profile).filter(Profile.nickname == nickname).first():
            nickname = f"{base_nickname}_{random.randint(100, 999)}"
            counter += 1
            if counter > 10:  # Cheksiz loop'dan himoya
                nickname = f"{base_nickname}_{random.randint(10000, 99999)}"
                break

        # Profil yaratish
        profile = Profile(
            user_id=user.id,
            nickname=nickname,
            coins=100,
            gems=0,
            level=1,
            experience=0
        )
        db.add(profile)
        db.commit()
        db.refresh(user)

    # Tokenlar yaratish
    token_data = {"sub": str(user.id), "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        is_new_user=is_new_user,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse, summary="Tokenni yangilash")
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh token yordamida yangi access token olish.
    """
    payload = decode_token(request.refresh_token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token noto'g'ri yoki eskirgan"
        )
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Noto'g'ri token turi"
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Foydalanuvchi topilmadi"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Foydalanuvchi bloklangan"
        )

    # Yangi tokenlar
    token_data = {"sub": str(user.id), "email": user.email}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        is_new_user=False,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout", summary="Chiqish")
def logout():
    """
    Logout - client tomonida tokenlarni o'chirish kerak.
    Server tomonida token blacklist qo'shish mumkin (keyinroq).
    """
    return {"message": "Muvaffaqiyatli chiqildi"}
