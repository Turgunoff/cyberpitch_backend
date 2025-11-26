# app/api/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.users import User, Profile

router = APIRouter()


class ProfileUpdateRequest(BaseModel):
    """Profil yangilash"""
    # Shaxsiy
    nickname: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    birth_date: Optional[str] = None  # "2000-01-15" format
    gender: Optional[str] = Field(None, max_length=10)
    region: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    language: Optional[str] = Field(None, max_length=10)
    
    # Ijtimoiy tarmoqlar
    telegram: Optional[str] = Field(None, max_length=50)
    instagram: Optional[str] = Field(None, max_length=50)
    youtube: Optional[str] = Field(None, max_length=100)
    discord: Optional[str] = Field(None, max_length=50)
    
    # O'yin
    pes_id: Optional[str] = Field(None, max_length=50)
    team_strength: Optional[int] = Field(None, ge=1000, le=5000)
    favorite_team: Optional[str] = Field(None, max_length=50)
    play_style: Optional[str] = Field(None, max_length=20)
    preferred_formation: Optional[str] = Field(None, max_length=10)
    available_hours: Optional[str] = Field(None, max_length=50)


class PhoneVerifyRequest(BaseModel):
    """Telefon tasdiqlash"""
    phone: str
    code: str


@router.get("/me", summary="Mening profilim")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Hozirgi foydalanuvchi ma'lumotlarini olish"""
    profile = current_user.profile
    
    # last_online yangilash
    if profile:
        profile.last_online = datetime.utcnow()
        db.commit()
    
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat(),
        "profile": _profile_to_dict(profile) if profile else None
    }


@router.patch("/me", summary="Profilni yangilash")
def update_my_profile(
    data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Profilni yangilash"""
    profile = current_user.profile
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil topilmadi"
        )
    
    # Nickname tekshirish
    if data.nickname and data.nickname != profile.nickname:
        existing = db.query(Profile).filter(
            Profile.nickname == data.nickname,
            Profile.id != profile.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu nickname allaqachon band"
            )
    
    # Yangilash
    update_data = data.model_dump(exclude_unset=True)
    
    # birth_date ni Date ga o'girish
    if 'birth_date' in update_data and update_data['birth_date']:
        from datetime import datetime
        try:
            update_data['birth_date'] = datetime.strptime(
                update_data['birth_date'], "%Y-%m-%d"
            ).date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Noto'g'ri sana formati. YYYY-MM-DD ko'rinishida kiriting"
            )
    
    for field, value in update_data.items():
        if hasattr(profile, field):
            setattr(profile, field, value)
    
    db.commit()
    db.refresh(profile)
    
    return {
        "message": "Profil yangilandi",
        "profile": _profile_to_dict(profile)
    }


@router.post("/me/verify-phone", summary="Telefon raqamni tasdiqlash")
def verify_phone(
    data: PhoneVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Telefon raqamni tasdiqlash (hozircha 123456 kod)"""
    profile = current_user.profile
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil topilmadi"
        )
    
    # Hozircha hardcoded kod
    if data.code != "123456":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kod noto'g'ri"
        )
    
    # Telefon va verified yangilash
    profile.phone = data.phone
    profile.is_verified = True
    
    db.commit()
    db.refresh(profile)
    
    return {
        "message": "Telefon tasdiqlandi",
        "is_verified": True,
        "phone": profile.phone
    }


@router.get("/{user_id}", summary="Boshqa user profili")
def get_user_profile(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Boshqa foydalanuvchi profilini ko'rish"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user or not user.profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foydalanuvchi topilmadi"
        )
    
    profile = user.profile
    
    # Agar profil yopiq bo'lsa
    if not profile.is_public:
        return {
            "id": str(profile.id),
            "nickname": profile.nickname,
            "avatar_url": profile.avatar_url,
            "is_public": False,
            "message": "Bu profil yopiq"
        }
    
    return _profile_to_dict(profile)


def _profile_to_dict(profile: Profile) -> dict:
    """Profile modeldan dict yaratish"""
    return {
        "id": str(profile.id),
        "user_id": str(profile.user_id),
        
        # Shaxsiy
        "nickname": profile.nickname,
        "full_name": profile.full_name,
        "phone": profile.phone,
        "birth_date": profile.birth_date.isoformat() if profile.birth_date else None,
        "gender": profile.gender,
        "avatar_url": profile.avatar_url,
        "region": profile.region,
        "bio": profile.bio,
        "language": profile.language,
        
        # Ijtimoiy
        "telegram": profile.telegram,
        "instagram": profile.instagram,
        "youtube": profile.youtube,
        "discord": profile.discord,
        
        # O'yin
        "pes_id": profile.pes_id,
        "team_strength": profile.team_strength,
        "favorite_team": profile.favorite_team,
        "play_style": profile.play_style,
        "preferred_formation": profile.preferred_formation,
        "available_hours": profile.available_hours,
        
        # Resurslar
        "coins": profile.coins,
        "gems": profile.gems,
        "level": profile.level,
        "experience": profile.experience,
        
        # Statistika
        "total_matches": profile.total_matches,
        "wins": profile.wins,
        "losses": profile.losses,
        "draws": profile.draws,
        "tournaments_won": profile.tournaments_won,
        "tournaments_played": profile.tournaments_played,
        "win_rate": profile.win_rate,
        
        # Status
        "is_verified": profile.is_verified,
        "is_pro": profile.is_pro,
        "is_public": profile.is_public,
        "show_stats": profile.show_stats,
        "last_online": profile.last_online.isoformat() if profile.last_online else None,
        
        "created_at": profile.created_at.isoformat(),
    }