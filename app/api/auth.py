# app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.users import User
from app.schemas.user import UserCreate, UserResponse
from passlib.context import CryptContext

router = APIRouter()

# Parolni shifrlash uchun sozlama
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # 1. Raqam band emasligini tekshiramiz
    existing_user = db.query(User).filter(User.phone_number == user.phone_number).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Bu raqam allaqachon ro'yxatdan o'tgan")

    # 2. Parolni shifrlaymiz
    hashed_password = pwd_context.hash(user.password)

    # 3. Yangi foydalanuvchi yaratamiz
    new_user = User(
        phone_number=user.phone_number,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user