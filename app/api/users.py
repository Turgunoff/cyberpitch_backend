# app/api/users.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func, desc
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.database import get_db

logger = logging.getLogger(__name__)
from app.core.security import get_current_user
from app.models.users import User, Profile, Friendship
from app.models.matches import Match1v1, GameStatus
from app.services.notification_service import (
    send_friend_request_notification_sync,
    send_friend_accepted_notification_sync,
)

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

    # Push Notifications
    onesignal_player_id: Optional[str] = Field(None, max_length=100)


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
        profile.last_online = datetime.now(timezone.utc)
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
    """Telefon raqamni tasdiqlash"""
    profile = current_user.profile

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil topilmadi"
        )

    # TODO: Production'da SMS OTP xizmati (Eskiz/PlayMobile) bilan almashtirish
    # Hozircha test uchun hardcoded kod
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


@router.get("/profile/{user_id}", summary="Boshqa user profili")
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


# ══════════════════════════════════════════════════════════
# O'YINCHI PROFILI (BATAFSIL)
# ══════════════════════════════════════════════════════════

@router.get("/player/{user_id}", summary="O'yinchi profili (batafsil)")
def get_player_profile(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    O'yinchi profili to'liq ma'lumotlar bilan:
    - Asosiy profil
    - Do'stlik holati
    - Head-to-head statistika
    - Oxirgi o'yinlar
    - Online status
    """
    target_user = db.query(User).filter(User.id == user_id).first()

    if not target_user or not target_user.profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O'yinchi topilmadi"
        )

    profile = target_user.profile

    # Online status
    five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    is_online = False
    if profile.last_online:
        last_online = profile.last_online
        if last_online.tzinfo is None:
            last_online = last_online.replace(tzinfo=timezone.utc)
        is_online = last_online >= five_minutes_ago

    # Do'stlik holati
    friendship_status = _get_friendship_status(db, current_user.id, UUID(user_id))

    # Head-to-head statistika
    h2h_stats = _get_head_to_head(db, current_user.id, UUID(user_id))

    # Oxirgi o'yinlar (5 ta)
    recent_matches = _get_recent_matches(db, UUID(user_id), limit=5)

    # Profil public bo'lmasa
    if not profile.is_public and friendship_status != "friends":
        return {
            "id": str(profile.user_id),
            "nickname": profile.nickname,
            "avatar_url": profile.avatar_url,
            "level": profile.level,
            "is_online": is_online,
            "is_public": False,
            "friendship_status": friendship_status,
            "message": "Bu profil yopiq. Do'st bo'ling ko'rish uchun."
        }

    return {
        "id": str(profile.user_id),
        "nickname": profile.nickname,
        "full_name": profile.full_name,
        "avatar_url": profile.avatar_url,
        "bio": profile.bio,
        "region": profile.region,

        # O'yin ma'lumotlari
        "level": profile.level,
        "experience": profile.experience,
        "team_strength": profile.team_strength,
        "favorite_team": profile.favorite_team,
        "play_style": profile.play_style,
        "preferred_formation": profile.preferred_formation,
        "available_hours": profile.available_hours,

        # Ijtimoiy
        "telegram": profile.telegram,
        "instagram": profile.instagram,
        "discord": profile.discord,

        # Statistika
        "stats": {
            "total_matches": profile.total_matches,
            "wins": profile.wins,
            "losses": profile.losses,
            "draws": profile.draws,
            "win_rate": profile.win_rate,
            "tournaments_won": profile.tournaments_won,
            "tournaments_played": profile.tournaments_played,
        },

        # Status
        "is_online": is_online,
        "last_online": profile.last_online.isoformat() if profile.last_online else None,
        "is_verified": profile.is_verified,
        "is_pro": profile.is_pro,
        "is_public": profile.is_public,

        # Do'stlik
        "friendship_status": friendship_status,

        # Head-to-head
        "head_to_head": h2h_stats,

        # Oxirgi o'yinlar
        "recent_matches": recent_matches,

        "member_since": profile.created_at.isoformat(),
    }


def _get_friendship_status(db: Session, user_id: UUID, target_id: UUID) -> str:
    """Do'stlik holatini aniqlash"""
    if user_id == target_id:
        return "self"

    friendship = db.query(Friendship).filter(
        or_(
            and_(Friendship.requester_id == user_id, Friendship.addressee_id == target_id),
            and_(Friendship.requester_id == target_id, Friendship.addressee_id == user_id)
        )
    ).first()

    if not friendship:
        return "none"

    if friendship.status == "accepted":
        return "friends"
    elif friendship.status == "pending":
        if friendship.requester_id == user_id:
            return "request_sent"
        else:
            return "request_received"
    elif friendship.status == "blocked":
        return "blocked"

    return "none"


def _get_head_to_head(db: Session, user_id: UUID, opponent_id: UUID) -> dict:
    """O'zaro o'yinlar statistikasi"""
    matches = db.query(Match1v1).filter(
        Match1v1.status == GameStatus.COMPLETED,
        or_(
            and_(Match1v1.player1_id == user_id, Match1v1.player2_id == opponent_id),
            and_(Match1v1.player1_id == opponent_id, Match1v1.player2_id == user_id)
        )
    ).all()

    total = len(matches)
    wins = 0
    losses = 0
    draws = 0

    for match in matches:
        if match.winner_id == user_id:
            wins += 1
        elif match.winner_id == opponent_id:
            losses += 1
        else:
            draws += 1

    return {
        "total_matches": total,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": round((wins / total * 100), 1) if total > 0 else 0
    }


def _get_recent_matches(db: Session, user_id: UUID, limit: int = 5) -> list:
    """Oxirgi o'yinlar"""
    matches = db.query(Match1v1).filter(
        Match1v1.status == GameStatus.COMPLETED,
        or_(
            Match1v1.player1_id == user_id,
            Match1v1.player2_id == user_id
        )
    ).order_by(desc(Match1v1.completed_at)).limit(limit).all()

    result = []
    for match in matches:
        # Opponent aniqlash
        is_player1 = match.player1_id == user_id
        opponent_id = match.player2_id if is_player1 else match.player1_id

        # Opponent profili
        opponent_profile = db.query(Profile).filter(Profile.user_id == opponent_id).first()

        # Natija
        if match.winner_id == user_id:
            match_result = "WIN"
        elif match.winner_id is None:
            match_result = "DRAW"
        else:
            match_result = "LOSS"

        # Score
        if is_player1:
            score = f"{match.player1_score or 0}-{match.player2_score or 0}"
        else:
            score = f"{match.player2_score or 0}-{match.player1_score or 0}"

        result.append({
            "id": str(match.id),
            "opponent": {
                "id": str(opponent_id),
                "nickname": opponent_profile.nickname if opponent_profile else "Unknown",
                "avatar_url": opponent_profile.avatar_url if opponent_profile else None,
            },
            "result": match_result,
            "score": score,
            "mode": match.mode.value,
            "played_at": match.completed_at.isoformat() if match.completed_at else None
        })

    return result


# ══════════════════════════════════════════════════════════
# DO'STLIK TIZIMI
# ══════════════════════════════════════════════════════════

@router.post("/friends/request/{user_id}", summary="Do'stlik so'rovi yuborish")
async def send_friend_request(
    user_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Do'stlik so'rovi yuborish"""
    if str(current_user.id) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O'zingizga so'rov yuborib bo'lmaydi"
        )

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foydalanuvchi topilmadi"
        )

    # Mavjud so'rov bormi tekshirish
    existing = db.query(Friendship).filter(
        or_(
            and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == UUID(user_id)),
            and_(Friendship.requester_id == UUID(user_id), Friendship.addressee_id == current_user.id)
        )
    ).first()

    if existing:
        if existing.status == "accepted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Siz allaqachon do'stsiz"
            )
        elif existing.status == "pending":
            if existing.requester_id == current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="So'rov allaqachon yuborilgan"
                )
            else:
                # Agar u yuborgan bo'lsa, avtomatik qabul qilish
                existing.status = "accepted"
                db.commit()
                return {"message": "Do'stlik tasdiqlandi", "status": "accepted"}
        elif existing.status == "blocked":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu foydalanuvchi bilan bog'lanib bo'lmaydi"
            )

    # Yangi so'rov yaratish
    friendship = Friendship(
        requester_id=current_user.id,
        addressee_id=UUID(user_id),
        status="pending"
    )
    db.add(friendship)
    db.commit()

    # Push Notification yuborish (background da)
    target_profile = db.query(Profile).filter(Profile.user_id == UUID(user_id)).first()
    logger.info(f"🔔 Target profile: {target_profile}")
    logger.info(f"🔔 OneSignal Player ID: {target_profile.onesignal_player_id if target_profile else 'No profile'}")

    if target_profile and target_profile.onesignal_player_id:
        requester_name = current_user.profile.nickname if current_user.profile else "O'yinchi"
        logger.info(f"🔔 Sending notification to: {target_profile.onesignal_player_id[:20]}...")
        background_tasks.add_task(
            send_friend_request_notification_sync,
            target_profile.onesignal_player_id,
            requester_name,
            str(current_user.id)
        )
    else:
        logger.warning(f"🔔 No OneSignal Player ID for user {user_id}")

    return {"message": "Do'stlik so'rovi yuborildi", "status": "pending"}


@router.post("/friends/accept/{user_id}", summary="Do'stlik so'rovini qabul qilish")
async def accept_friend_request(
    user_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Do'stlik so'rovini qabul qilish"""
    friendship = db.query(Friendship).filter(
        Friendship.requester_id == UUID(user_id),
        Friendship.addressee_id == current_user.id,
        Friendship.status == "pending"
    ).first()

    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="So'rov topilmadi"
        )

    friendship.status = "accepted"
    db.commit()

    # Push Notification yuborish (so'rov yuborgan odamga)
    requester_profile = db.query(Profile).filter(Profile.user_id == UUID(user_id)).first()
    if requester_profile and requester_profile.onesignal_player_id:
        friend_name = current_user.profile.nickname if current_user.profile else "O'yinchi"
        background_tasks.add_task(
            send_friend_accepted_notification_sync,
            requester_profile.onesignal_player_id,
            friend_name,
            str(current_user.id)
        )

    return {"message": "Do'stlik tasdiqlandi", "status": "accepted"}


@router.post("/friends/decline/{user_id}", summary="Do'stlik so'rovini rad etish")
def decline_friend_request(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Do'stlik so'rovini rad etish"""
    friendship = db.query(Friendship).filter(
        Friendship.requester_id == UUID(user_id),
        Friendship.addressee_id == current_user.id,
        Friendship.status == "pending"
    ).first()

    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="So'rov topilmadi"
        )

    db.delete(friendship)
    db.commit()

    return {"message": "So'rov rad etildi"}


@router.delete("/friends/{user_id}", summary="Do'stlikdan chiqarish")
def remove_friend(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Do'stlikdan chiqarish"""
    friendship = db.query(Friendship).filter(
        or_(
            and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == UUID(user_id)),
            and_(Friendship.requester_id == UUID(user_id), Friendship.addressee_id == current_user.id)
        ),
        Friendship.status == "accepted"
    ).first()

    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Do'stlik topilmadi"
        )

    db.delete(friendship)
    db.commit()

    return {"message": "Do'stlikdan chiqarildi"}


@router.get("/friends", summary="Do'stlar ro'yxati")
def get_friends_list(
    status_filter: str = Query("all", pattern="^(all|online)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Do'stlar ro'yxatini olish"""
    five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)

    # Do'stliklarni olish
    friendships = db.query(Friendship).filter(
        or_(
            Friendship.requester_id == current_user.id,
            Friendship.addressee_id == current_user.id
        ),
        Friendship.status == "accepted"
    ).all()

    friends = []
    for f in friendships:
        # Do'st ID ni aniqlash
        friend_id = f.addressee_id if f.requester_id == current_user.id else f.requester_id
        friend_profile = db.query(Profile).filter(Profile.user_id == friend_id).first()

        if not friend_profile:
            continue

        # Online status
        is_online = False
        if friend_profile.last_online:
            last_online = friend_profile.last_online
            if last_online.tzinfo is None:
                last_online = last_online.replace(tzinfo=timezone.utc)
            is_online = last_online >= five_minutes_ago

        # Filter
        if status_filter == "online" and not is_online:
            continue

        friends.append({
            "id": str(friend_id),
            "nickname": friend_profile.nickname,
            "avatar_url": friend_profile.avatar_url,
            "level": friend_profile.level,
            "is_online": is_online,
            "last_online": friend_profile.last_online.isoformat() if friend_profile.last_online else None,
            "win_rate": friend_profile.win_rate
        })

    # Online birinchi, keyin nickname bo'yicha
    friends.sort(key=lambda x: (not x["is_online"], x["nickname"].lower()))

    return {
        "friends": friends,
        "total": len(friends),
        "online_count": sum(1 for f in friends if f["is_online"])
    }


@router.get("/friends/requests", summary="Kutilayotgan do'stlik so'rovlari")
def get_friend_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kutilayotgan do'stlik so'rovlarini olish"""
    requests = db.query(Friendship).filter(
        Friendship.addressee_id == current_user.id,
        Friendship.status == "pending"
    ).order_by(desc(Friendship.created_at)).all()

    result = []
    for r in requests:
        requester_profile = db.query(Profile).filter(Profile.user_id == r.requester_id).first()

        if requester_profile:
            result.append({
                "id": str(r.requester_id),
                "nickname": requester_profile.nickname,
                "avatar_url": requester_profile.avatar_url,
                "level": requester_profile.level,
                "win_rate": requester_profile.win_rate,
                "requested_at": r.created_at.isoformat()
            })

    return {
        "requests": result,
        "count": len(result)
    }