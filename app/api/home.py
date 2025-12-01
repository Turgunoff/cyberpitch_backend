# app/api/home.py
"""
Home screen uchun API
Dashboard ma'lumotlari, online users, featured tournaments
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.users import User, Profile
from app.models.tournaments import Tournament, TournamentStatus, TournamentParticipant
from app.models.matches import Match1v1, GameStatus

router = APIRouter()


@router.get("/dashboard", summary="Home dashboard ma'lumotlari")
def get_home_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Home screen uchun barcha kerakli ma'lumotlar
    - User profili
    - Online users soni
    - Aktiv turnirlar
    - Oxirgi matchlar
    - Statistika
    """
    profile = current_user.profile

    # Online users (oxirgi 5 daqiqada aktiv)
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    online_count = db.query(func.count(Profile.id)).filter(
        Profile.last_online >= five_minutes_ago
    ).scalar() or 0

    # Agar kam bo'lsa, minimum ko'rsatish
    if online_count < 100:
        online_count = 100 + (datetime.utcnow().minute * 3)  # Dynamic fake count

    # User statistikasi
    user_stats = {
        "total_matches": profile.total_matches if profile else 0,
        "wins": profile.wins if profile else 0,
        "losses": profile.losses if profile else 0,
        "draws": profile.draws if profile else 0,
        "win_rate": profile.win_rate if profile else 0,
        "tournaments_played": profile.tournaments_played if profile else 0,
        "tournaments_won": profile.tournaments_won if profile else 0,
        "coins": profile.coins if profile else 0,
        "gems": profile.gems if profile else 0,
        "level": profile.level if profile else 1,
        "experience": profile.experience if profile else 0,
    }

    # Aktiv/kelayotgan turnirlar
    active_tournaments = db.query(Tournament).filter(
        Tournament.status.in_([TournamentStatus.REGISTRATION, TournamentStatus.LIVE])
    ).order_by(desc(Tournament.is_featured), desc(Tournament.created_at)).limit(5).all()

    tournaments_data = []
    for t in active_tournaments:
        participant_count = db.query(func.count(TournamentParticipant.id)).filter(
            TournamentParticipant.tournament_id == t.id
        ).scalar() or 0

        # User qo'shilganmi?
        is_joined = db.query(TournamentParticipant).filter(
            TournamentParticipant.tournament_id == t.id,
            TournamentParticipant.user_id == current_user.id
        ).first() is not None

        tournaments_data.append({
            "id": str(t.id),
            "name": t.name,
            "status": t.status.value,
            "format": t.format.value,
            "prize_pool": t.prize_pool,
            "entry_fee": t.entry_fee,
            "max_participants": t.max_participants,
            "participant_count": participant_count,
            "start_time": t.start_time.isoformat() if t.start_time else None,
            "is_featured": t.is_featured,
            "is_joined": is_joined,
        })

    # Oxirgi 5 ta match (user ning)
    recent_matches = db.query(Match1v1).filter(
        Match1v1.status == GameStatus.COMPLETED,
        ((Match1v1.player1_id == current_user.id) | (Match1v1.player2_id == current_user.id))
    ).order_by(desc(Match1v1.completed_at)).limit(5).all()

    matches_data = []
    for m in recent_matches:
        # Opponent aniqlash
        opponent_id = m.player2_id if m.player1_id == current_user.id else m.player1_id
        opponent_profile = db.query(Profile).filter(Profile.user_id == opponent_id).first()

        # Natija
        if m.winner_id == current_user.id:
            result = "WIN"
        elif m.winner_id is None:
            result = "DRAW"
        else:
            result = "LOSS"

        # Score
        if m.player1_id == current_user.id:
            score = f"{m.player1_score or 0}-{m.player2_score or 0}"
            rating_change = m.player1_rating_change
        else:
            score = f"{m.player2_score or 0}-{m.player1_score or 0}"
            rating_change = m.player2_rating_change

        matches_data.append({
            "id": str(m.id),
            "opponent_nickname": opponent_profile.nickname if opponent_profile else "Unknown",
            "opponent_avatar": opponent_profile.avatar_url if opponent_profile else None,
            "result": result,
            "score": score,
            "rating_change": rating_change,
            "mode": m.mode.value,
            "played_at": m.completed_at.isoformat() if m.completed_at else None,
        })

    # Pending challenges (kutilayotgan)
    pending_challenges = db.query(func.count(Match1v1.id)).filter(
        Match1v1.player2_id == current_user.id,
        Match1v1.status == GameStatus.PENDING
    ).scalar() or 0

    return {
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "nickname": profile.nickname if profile else None,
            "avatar_url": profile.avatar_url if profile else None,
            "level": profile.level if profile else 1,
            "coins": profile.coins if profile else 0,
            "gems": profile.gems if profile else 0,
        },
        "stats": user_stats,
        "online_users": online_count,
        "pending_challenges": pending_challenges,
        "tournaments": tournaments_data,
        "recent_matches": matches_data,
    }


@router.get("/leaderboard", summary="Leaderboard")
def get_leaderboard(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Top o'yinchilar ro'yxati (win rate bo'yicha)"""
    # Minimum 10 ta o'yin o'ynagan userlar
    leaders = db.query(Profile).filter(
        Profile.total_matches >= 10,
        Profile.nickname.isnot(None)
    ).order_by(
        desc(Profile.wins),
        desc(Profile.total_matches)
    ).limit(limit).all()

    result = []
    for i, p in enumerate(leaders):
        result.append({
            "rank": i + 1,
            "user_id": str(p.user_id),
            "nickname": p.nickname,
            "avatar_url": p.avatar_url,
            "level": p.level,
            "total_matches": p.total_matches,
            "wins": p.wins,
            "win_rate": p.win_rate,
            "tournaments_won": p.tournaments_won,
        })

    return {"leaderboard": result}
