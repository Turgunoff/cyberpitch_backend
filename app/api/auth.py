from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.users import User, Profile
from app.schemas.auth import EmailLoginRequest, VerifyOTPRequest, TokenResponse
from app.services.otp_service import generate_and_save_otp, verify_otp_in_redis
from app.core.config import settings
from jose import jwt
from datetime import timedelta

router = APIRouter()

# 1. KOD YUBORISH
@router.post("/send-code")
def send_code(request: EmailLoginRequest):
    generate_and_save_otp(request.email)
    return {"message": "Tasdiqlash kodi terminalga chiqarildi (Dev Mode)"}

# 2. KODNI TEKSHIRISH VA KIRISH
@router.post("/verify-code", response_model=TokenResponse)
def verify_code(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    # Redisdan tekshirish
    if not verify_otp_in_redis(request.email, request.code):
        raise HTTPException(status_code=400, detail="Kod noto'g'ri yoki eskirgan")

    # 2. Userni qidirish
    user = db.query(User).filter(User.email == request.email).first()
    is_new_user = False

    if not user:
        is_new_user = True
        user = User(email=request.email)
        db.add(user)
        db.commit()
        db.refresh(user)

        # --- YANGI LOGIKA: NICKNAME YARATISH ---
        # Email: "eldor@gmail.com" -> Nickname: "eldor"
        auto_nickname = request.email.split("@")[0]
        
        # Agar bunday nick band bo'lsa, orqasiga raqam qo'shamiz (xavfsizlik uchun)
        if db.query(Profile).filter(Profile.nickname == auto_nickname).first():
            import random
            auto_nickname = f"{auto_nickname}_{random.randint(100, 999)}"

        # Profil yaratish (To'ldirilgan holda)
        profile = Profile(
            user_id=user.id,
            nickname=auto_nickname,  # <-- Avtomatik nickname
            coins=100,
            gems=0,
            level=1
        )
        db.add(profile)
        db.commit()

    # Token yaratish
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": str(user.id), "email": user.email}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return {
        "access_token": encoded_jwt,
        "token_type": "bearer",
        "is_new_user": is_new_user
    }