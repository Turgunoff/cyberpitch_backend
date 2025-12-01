# app/api/matches.py
"""
1vs1 o'yinlar API
O'yin yaratish, qabul qilish, natija yuborish va tarix
Matchmaking queue va online players
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func, desc
from typing import Optional, Dict
from uuid import UUID
from datetime import datetime, timedelta
import random

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.users import User, Profile
from app.models.matches import Match1v1, GameMode, GameStatus

# In-memory matchmaking queue (production'da Redis ishlatiladi)
matchmaking_queue: Dict[str, dict] = {}  # user_id -> {user_data, joined_at, mode}
from app.schemas.match import (
    MatchCreate,
    MatchResultSubmit,
    MatchResponse,
    MatchHistoryItem,
    MatchHistoryResponse,
    MatchOpponentInfo,
    UserMatchStats,
    UserStatsResponse
)

router = APIRouter()


# ══════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_opponent_info(db: Session, user_id: UUID) -> MatchOpponentInfo:
    """Opponent ma'lumotlarini olish"""
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    return MatchOpponentInfo(
        id=user_id,
        nickname=profile.nickname if profile else None,
        avatar_url=profile.avatar_url if profile else None,
        team_strength=profile.team_strength if profile else None
    )


def get_match_result_for_user(match: Match1v1, user_id: UUID) -> str:
    """User uchun natijani aniqlash (WIN/LOSS/DRAW)"""
    if match.winner_id is None:
        return "DRAW"
    if match.winner_id == user_id:
        return "WIN"
    return "LOSS"


def get_score_for_user(match: Match1v1, user_id: UUID) -> str:
    """User nuqtai nazaridan natijani ko'rsatish"""
    if match.player1_score is None or match.player2_score is None:
        return "-"
    if match.player1_id == user_id:
        return f"{match.player1_score}-{match.player2_score}"
    return f"{match.player2_score}-{match.player1_score}"


def get_rating_change_for_user(match: Match1v1, user_id: UUID) -> int:
    """User uchun reyting o'zgarishini olish"""
    if match.player1_id == user_id:
        return match.player1_rating_change
    return match.player2_rating_change


def calculate_elo_change(winner_rating: int, loser_rating: int, k_factor: int = 32) -> tuple[int, int]:
    """ELO reyting o'zgarishini hisoblash"""
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 - expected_winner

    winner_change = int(k_factor * (1 - expected_winner))
    loser_change = int(k_factor * (0 - expected_loser))

    return winner_change, loser_change


# ══════════════════════════════════════════════════════════
# MATCH HISTORY
# ══════════════════════════════════════════════════════════

@router.get("/history", response_model=MatchHistoryResponse, summary="O'yin tarixi")
def get_match_history(
    mode: Optional[GameMode] = None,
    result: Optional[str] = Query(None, pattern="^(WIN|LOSS|DRAW)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Foydalanuvchining o'yin tarixini olish
    Filtrlash: mode (ranked/friendly/challenge), result (WIN/LOSS/DRAW)
    """
    # Faqat yakunlangan o'yinlar
    query = db.query(Match1v1).filter(
        Match1v1.status == GameStatus.COMPLETED,
        or_(
            Match1v1.player1_id == current_user.id,
            Match1v1.player2_id == current_user.id
        )
    )

    # Mode filtri
    if mode:
        query = query.filter(Match1v1.mode == mode)

    # Eng yangilarini olish
    query = query.order_by(desc(Match1v1.completed_at))

    # Total
    total = query.count()

    # Sahifalash
    matches = query.offset((page - 1) * per_page).limit(per_page).all()

    # Response yaratish
    history_items = []
    for match in matches:
        # Opponent aniqlash
        opponent_id = match.player2_id if match.player1_id == current_user.id else match.player1_id
        opponent_info = get_opponent_info(db, opponent_id)

        # Natija
        match_result = get_match_result_for_user(match, current_user.id)

        # Result filtri
        if result and match_result != result:
            continue

        history_items.append(MatchHistoryItem(
            id=match.id,
            mode=match.mode,
            status=match.status,
            opponent=opponent_info,
            score=get_score_for_user(match, current_user.id),
            result=match_result,
            rating_change=get_rating_change_for_user(match, current_user.id),
            played_at=match.completed_at or match.created_at
        ))

    return MatchHistoryResponse(
        matches=history_items,
        total=total,
        page=page,
        per_page=per_page,
        has_next=page * per_page < total,
        has_prev=page > 1
    )


@router.get("/stats", response_model=UserStatsResponse, summary="O'yin statistikasi")
def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Foydalanuvchining to'liq o'yin statistikasini olish
    """
    profile = current_user.profile

    # Barcha yakunlangan o'yinlar
    matches = db.query(Match1v1).filter(
        Match1v1.status == GameStatus.COMPLETED,
        or_(
            Match1v1.player1_id == current_user.id,
            Match1v1.player2_id == current_user.id
        )
    ).order_by(desc(Match1v1.completed_at)).all()

    # Asosiy statistika
    total_matches = len(matches)
    wins = 0
    losses = 0
    draws = 0
    goals_scored = 0
    goals_conceded = 0
    clean_sheets = 0

    # Ranked statistika
    ranked_matches = 0
    ranked_wins = 0

    # Streak hisoblash
    current_streak = 0
    longest_win_streak = 0
    longest_loss_streak = 0
    temp_win_streak = 0
    temp_loss_streak = 0

    # Recent form (oxirgi 5 ta)
    recent_form = []

    for i, match in enumerate(matches):
        result = get_match_result_for_user(match, current_user.id)

        # Win/Loss/Draw
        if result == "WIN":
            wins += 1
            temp_win_streak += 1
            temp_loss_streak = 0
            longest_win_streak = max(longest_win_streak, temp_win_streak)
        elif result == "LOSS":
            losses += 1
            temp_loss_streak += 1
            temp_win_streak = 0
            longest_loss_streak = max(longest_loss_streak, temp_loss_streak)
        else:
            draws += 1
            temp_win_streak = 0
            temp_loss_streak = 0

        # Goals
        if match.player1_id == current_user.id:
            my_score = match.player1_score or 0
            opp_score = match.player2_score or 0
        else:
            my_score = match.player2_score or 0
            opp_score = match.player1_score or 0

        goals_scored += my_score
        goals_conceded += opp_score
        if opp_score == 0:
            clean_sheets += 1

        # Ranked
        if match.mode == GameMode.RANKED:
            ranked_matches += 1
            if result == "WIN":
                ranked_wins += 1

        # Recent form (oxirgi 5)
        if i < 5:
            recent_form.append(result[0])  # "W", "L", "D"

    # Current streak (birinchi o'yindan)
    if matches:
        first_result = get_match_result_for_user(matches[0], current_user.id)
        if first_result == "WIN":
            # Win streak sanash
            for match in matches:
                if get_match_result_for_user(match, current_user.id) == "WIN":
                    current_streak += 1
                else:
                    break
        elif first_result == "LOSS":
            for match in matches:
                if get_match_result_for_user(match, current_user.id) == "LOSS":
                    current_streak -= 1
                else:
                    break

    # Win rate
    win_rate = round((wins / total_matches * 100), 2) if total_matches > 0 else 0.0
    avg_goals = round(goals_scored / total_matches, 2) if total_matches > 0 else 0.0

    # Tournament stats (Profile'dan)
    tournaments_played = profile.tournaments_played if profile else 0
    tournaments_won = profile.tournaments_won if profile else 0

    overview = UserMatchStats(
        total_matches=total_matches,
        wins=wins,
        losses=losses,
        draws=draws,
        win_rate=win_rate,
        goals_scored=goals_scored,
        goals_conceded=goals_conceded,
        avg_goals_per_match=avg_goals,
        clean_sheets=clean_sheets,
        current_streak=current_streak,
        longest_win_streak=longest_win_streak,
        longest_loss_streak=longest_loss_streak,
        ranked_matches=ranked_matches,
        ranked_wins=ranked_wins,
        ranked_rating=1000,  # TODO: ELO system
        tournaments_played=tournaments_played,
        tournaments_won=tournaments_won,
        best_tournament_position=1 if tournaments_won > 0 else None,
        total_tournament_earnings=0  # TODO: earnings tracking
    )

    # Monthly stats (oxirgi 30 kun)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    monthly_matches = [m for m in matches if m.completed_at and m.completed_at >= thirty_days_ago]
    monthly_wins = sum(1 for m in monthly_matches if get_match_result_for_user(m, current_user.id) == "WIN")

    monthly_stats = {
        "matches": len(monthly_matches),
        "wins": monthly_wins,
        "losses": len(monthly_matches) - monthly_wins,
        "win_rate": round((monthly_wins / len(monthly_matches) * 100), 2) if monthly_matches else 0
    }

    return UserStatsResponse(
        overview=overview,
        recent_form=recent_form,
        monthly_stats=monthly_stats
    )


# ══════════════════════════════════════════════════════════
# CREATE & MANAGE MATCHES
# ══════════════════════════════════════════════════════════

@router.post("/challenge", status_code=status.HTTP_201_CREATED, summary="Challenge yuborish")
def create_challenge(
    data: MatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Raqibga challenge yuborish (1vs1 o'yin taklifi)
    """
    # O'ziga challenge yuborish mumkin emas
    if data.opponent_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O'zingizga challenge yuborib bo'lmaydi"
        )

    # Opponent mavjudligini tekshirish
    opponent = db.query(User).filter(User.id == data.opponent_id).first()
    if not opponent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Raqib topilmadi"
        )

    # Active challenge mavjudligini tekshirish
    existing = db.query(Match1v1).filter(
        Match1v1.status.in_([GameStatus.PENDING, GameStatus.ACCEPTED, GameStatus.PLAYING]),
        or_(
            and_(Match1v1.player1_id == current_user.id, Match1v1.player2_id == data.opponent_id),
            and_(Match1v1.player1_id == data.opponent_id, Match1v1.player2_id == current_user.id)
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu raqib bilan allaqachon aktiv o'yin mavjud"
        )

    # Bet amount tekshirish (challenge mode)
    if data.mode == GameMode.CHALLENGE and data.bet_amount > 0:
        profile = current_user.profile
        if not profile or profile.coins < data.bet_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Yetarli coin yo'q. Kerak: {data.bet_amount}"
            )

    # Match yaratish
    match = Match1v1(
        player1_id=current_user.id,
        player2_id=data.opponent_id,
        mode=data.mode,
        bet_amount=data.bet_amount,
        status=GameStatus.PENDING
    )

    db.add(match)
    db.commit()
    db.refresh(match)

    return {
        "message": "Challenge yuborildi",
        "match_id": str(match.id),
        "opponent": get_opponent_info(db, data.opponent_id)
    }


@router.post("/{match_id}/accept", summary="Challenge qabul qilish")
def accept_challenge(
    match_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Challenge'ni qabul qilish"""
    match = db.query(Match1v1).filter(Match1v1.id == match_id).first()

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O'yin topilmadi"
        )

    # Faqat player2 qabul qila oladi
    if match.player2_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu challenge'ni qabul qila olmaysiz"
        )

    if match.status != GameStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu challenge qabul qilib bo'lmaydi"
        )

    # Bet amount tekshirish
    if match.bet_amount > 0:
        profile = current_user.profile
        if not profile or profile.coins < match.bet_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Yetarli coin yo'q. Kerak: {match.bet_amount}"
            )
        # Ikki o'yinchidan ham pul ushlab turish
        # player1 dan
        p1_profile = db.query(Profile).filter(Profile.user_id == match.player1_id).first()
        if p1_profile:
            p1_profile.coins -= match.bet_amount
        # player2 dan
        profile.coins -= match.bet_amount

    match.status = GameStatus.ACCEPTED
    match.accepted_at = datetime.utcnow()

    db.commit()

    return {"message": "Challenge qabul qilindi", "match_id": str(match.id)}


@router.post("/{match_id}/decline", summary="Challenge rad etish")
def decline_challenge(
    match_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Challenge'ni rad etish"""
    match = db.query(Match1v1).filter(Match1v1.id == match_id).first()

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O'yin topilmadi"
        )

    # Faqat player2 rad eta oladi
    if match.player2_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu challenge'ni rad eta olmaysiz"
        )

    if match.status != GameStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu challenge rad etib bo'lmaydi"
        )

    match.status = GameStatus.CANCELLED
    db.commit()

    return {"message": "Challenge rad etildi"}


@router.post("/{match_id}/result", summary="Natija yuborish")
def submit_result(
    match_id: UUID,
    data: MatchResultSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """O'yin natijasini yuborish"""
    match = db.query(Match1v1).filter(Match1v1.id == match_id).first()

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="O'yin topilmadi"
        )

    # Faqat o'yinchilar yuborishi mumkin
    if current_user.id not in [match.player1_id, match.player2_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu o'yinda qatnashmayapsiz"
        )

    if match.status not in [GameStatus.ACCEPTED, GameStatus.PLAYING, GameStatus.RESULT_SUBMITTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu o'yin uchun natija yuborib bo'lmaydi"
        )

    # Natijani saqlash
    is_player1 = current_user.id == match.player1_id
    score_str = f"{data.my_score}-{data.opponent_score}"

    if is_player1:
        match.player1_claimed_score = score_str
        match.player1_submitted = True
        if data.screenshot_url:
            match.player1_screenshot = data.screenshot_url
    else:
        # Player2 uchun teskari
        match.player2_claimed_score = f"{data.opponent_score}-{data.my_score}"
        match.player2_submitted = True
        if data.screenshot_url:
            match.player2_screenshot = data.screenshot_url

    # Ikkala o'yinchi ham yuborgan bo'lsa
    if match.player1_submitted and match.player2_submitted:
        # Natijalar mos kelsa
        if match.player1_claimed_score == match.player2_claimed_score:
            # Natijani tasdiqlash
            scores = match.player1_claimed_score.split("-")
            match.player1_score = int(scores[0])
            match.player2_score = int(scores[1])

            # Winner aniqlash
            if match.player1_score > match.player2_score:
                match.winner_id = match.player1_id
            elif match.player2_score > match.player1_score:
                match.winner_id = match.player2_id

            # Reyting o'zgarishi (ranked mode)
            if match.mode == GameMode.RANKED and match.winner_id:
                # Oddiy +25/-25 hozircha
                if match.winner_id == match.player1_id:
                    match.player1_rating_change = 25
                    match.player2_rating_change = -25
                else:
                    match.player1_rating_change = -25
                    match.player2_rating_change = 25

            # Challenge prize
            if match.bet_amount > 0 and match.winner_id:
                winner_profile = db.query(Profile).filter(Profile.user_id == match.winner_id).first()
                if winner_profile:
                    winner_profile.coins += match.bet_amount * 2  # Ikki o'yinchining puli

            # Profillarni yangilash
            for player_id in [match.player1_id, match.player2_id]:
                profile = db.query(Profile).filter(Profile.user_id == player_id).first()
                if profile:
                    profile.total_matches += 1
                    if match.winner_id == player_id:
                        profile.wins += 1
                    elif match.winner_id is None:
                        profile.draws += 1
                    else:
                        profile.losses += 1

            match.status = GameStatus.COMPLETED
            match.completed_at = datetime.utcnow()
        else:
            # Natijalar mos kelmasa - dispute
            match.status = GameStatus.DISPUTED
            match.dispute_reason = "Natijalar mos kelmadi"
    else:
        match.status = GameStatus.RESULT_SUBMITTED

    db.commit()

    return {
        "message": "Natija qabul qilindi",
        "status": match.status.value,
        "is_completed": match.status == GameStatus.COMPLETED
    }


# ══════════════════════════════════════════════════════════
# PENDING CHALLENGES
# ══════════════════════════════════════════════════════════

@router.get("/pending", summary="Kutilayotgan challenge'lar")
def get_pending_challenges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Qabul qilish kerak bo'lgan challenge'lar"""
    challenges = db.query(Match1v1).filter(
        Match1v1.player2_id == current_user.id,
        Match1v1.status == GameStatus.PENDING
    ).order_by(desc(Match1v1.created_at)).all()

    result = []
    for match in challenges:
        opponent_info = get_opponent_info(db, match.player1_id)
        result.append({
            "id": str(match.id),
            "mode": match.mode.value,
            "bet_amount": match.bet_amount,
            "challenger": opponent_info,
            "created_at": match.created_at
        })

    return {"challenges": result, "count": len(result)}


@router.get("/active", summary="Aktiv o'yinlar")
def get_active_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Hozirgi aktiv o'yinlar (natija kutilayotgan)"""
    matches = db.query(Match1v1).filter(
        Match1v1.status.in_([GameStatus.ACCEPTED, GameStatus.PLAYING, GameStatus.RESULT_SUBMITTED]),
        or_(
            Match1v1.player1_id == current_user.id,
            Match1v1.player2_id == current_user.id
        )
    ).order_by(desc(Match1v1.created_at)).all()

    result = []
    for match in matches:
        opponent_id = match.player2_id if match.player1_id == current_user.id else match.player1_id
        opponent_info = get_opponent_info(db, opponent_id)

        # User natija yuborganmi
        is_player1 = match.player1_id == current_user.id
        has_submitted = match.player1_submitted if is_player1 else match.player2_submitted

        result.append({
            "id": str(match.id),
            "mode": match.mode.value,
            "status": match.status.value,
            "bet_amount": match.bet_amount,
            "opponent": opponent_info,
            "has_submitted_result": has_submitted,
            "created_at": match.created_at
        })

    return {"matches": result, "count": len(result)}


# ══════════════════════════════════════════════════════════
# MATCHMAKING QUEUE
# ══════════════════════════════════════════════════════════

@router.post("/queue/join", summary="Matchmaking queuega qo'shilish")
def join_matchmaking_queue(
    mode: GameMode = GameMode.RANKED,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Avtomatik raqib topish uchun queuega qo'shilish
    """
    user_id = str(current_user.id)
    profile = current_user.profile

    # Allaqachon queueda bo'lsa
    if user_id in matchmaking_queue:
        return {
            "status": "already_in_queue",
            "message": "Siz allaqachon queuedasiz",
            "position": list(matchmaking_queue.keys()).index(user_id) + 1
        }

    # User ma'lumotlarini saqlash
    matchmaking_queue[user_id] = {
        "user_id": user_id,
        "nickname": profile.nickname if profile else "Player",
        "avatar_url": profile.avatar_url if profile else None,
        "level": profile.level if profile else 1,
        "rating": 1000,  # TODO: ELO rating
        "wins": profile.wins if profile else 0,
        "total_matches": profile.total_matches if profile else 0,
        "mode": mode.value,
        "joined_at": datetime.utcnow().isoformat()
    }

    # Raqib qidirish
    match_found = None
    for other_id, other_data in list(matchmaking_queue.items()):
        if other_id != user_id and other_data["mode"] == mode.value:
            # Match topildi!
            match_found = other_data

            # Match yaratish
            match = Match1v1(
                player1_id=UUID(other_id),
                player2_id=current_user.id,
                mode=mode,
                status=GameStatus.ACCEPTED  # Avtomatik qabul
            )
            db.add(match)
            db.commit()
            db.refresh(match)

            # Ikkalasini ham queuedan olib tashlash
            del matchmaking_queue[other_id]
            del matchmaking_queue[user_id]

            return {
                "status": "match_found",
                "message": "Raqib topildi!",
                "match_id": str(match.id),
                "opponent": {
                    "id": other_id,
                    "nickname": other_data["nickname"],
                    "avatar_url": other_data["avatar_url"],
                    "level": other_data["level"],
                    "wins": other_data["wins"],
                    "total_matches": other_data["total_matches"]
                }
            }

    # Raqib topilmadi, queueda kutish
    position = len(matchmaking_queue)
    return {
        "status": "searching",
        "message": "Raqib qidirilmoqda...",
        "position": position,
        "queue_size": len(matchmaking_queue)
    }


@router.delete("/queue/leave", summary="Queuedan chiqish")
def leave_matchmaking_queue(
    current_user: User = Depends(get_current_user)
):
    """Matchmaking queuedan chiqish"""
    user_id = str(current_user.id)

    if user_id in matchmaking_queue:
        del matchmaking_queue[user_id]
        return {"status": "left", "message": "Queuedan chiqdingiz"}

    return {"status": "not_in_queue", "message": "Siz queueda emassiz"}


@router.get("/queue/status", summary="Queue holati")
def get_queue_status(
    current_user: User = Depends(get_current_user)
):
    """Queuedagi holatni tekshirish"""
    user_id = str(current_user.id)

    if user_id not in matchmaking_queue:
        return {
            "status": "not_in_queue",
            "in_queue": False
        }

    position = list(matchmaking_queue.keys()).index(user_id) + 1
    user_data = matchmaking_queue[user_id]

    return {
        "status": "searching",
        "in_queue": True,
        "position": position,
        "queue_size": len(matchmaking_queue),
        "mode": user_data["mode"],
        "joined_at": user_data["joined_at"]
    }


# ══════════════════════════════════════════════════════════
# ONLINE PLAYERS
# ══════════════════════════════════════════════════════════

@router.get("/online-players", summary="Online o'yinchilar")
def get_online_players(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Hozir online bo'lgan o'yinchilar ro'yxati
    Challenge yuborish uchun
    """
    # Oxirgi 5 daqiqada aktiv bo'lganlar
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)

    online_profiles = db.query(Profile).filter(
        Profile.last_online >= five_minutes_ago,
        Profile.user_id != current_user.id,  # O'zini chiqarish
        Profile.nickname.isnot(None)
    ).order_by(desc(Profile.last_online)).limit(limit).all()

    players = []
    for p in online_profiles:
        # Bu o'yinchi bilan aktiv o'yin bormi?
        has_active_match = db.query(Match1v1).filter(
            Match1v1.status.in_([GameStatus.PENDING, GameStatus.ACCEPTED, GameStatus.PLAYING]),
            or_(
                and_(Match1v1.player1_id == current_user.id, Match1v1.player2_id == p.user_id),
                and_(Match1v1.player1_id == p.user_id, Match1v1.player2_id == current_user.id)
            )
        ).first() is not None

        win_rate = round((p.wins / p.total_matches * 100), 1) if p.total_matches > 0 else 0

        players.append({
            "id": str(p.user_id),
            "nickname": p.nickname,
            "avatar_url": p.avatar_url,
            "level": p.level,
            "wins": p.wins,
            "total_matches": p.total_matches,
            "win_rate": win_rate,
            "has_active_match": has_active_match,
            "last_online": p.last_online.isoformat() if p.last_online else None
        })

    return {
        "players": players,
        "count": len(players),
        "total_online": db.query(func.count(Profile.id)).filter(
            Profile.last_online >= five_minutes_ago
        ).scalar() or 0
    }


@router.post("/update-online", summary="Online statusni yangilash")
def update_online_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Foydalanuvchining online statusini yangilash
    Har 30 sekundda chaqiriladi
    """
    profile = current_user.profile
    if profile:
        profile.last_online = datetime.utcnow()
        db.commit()

    return {"status": "updated"}


@router.get("/players", summary="Barcha o'yinchilar")
def get_all_players(
    filter: str = Query("all", pattern="^(all|online)$"),
    search: Optional[str] = Query(None, min_length=2, max_length=50),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Barcha o'yinchilar ro'yxati
    - filter: 'all' - hammasi, 'online' - faqat onlinelar
    - search: nickname bo'yicha qidirish
    - Sort: online bo'lganlar birinchi, keyin vaqt bo'yicha
    """
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)

    query = db.query(Profile).filter(
        Profile.user_id != current_user.id,  # O'zini chiqarish
        Profile.nickname.isnot(None)
    )

    # Filter: faqat online
    if filter == "online":
        query = query.filter(Profile.last_online >= five_minutes_ago)

    # Search: nickname bo'yicha
    if search:
        query = query.filter(Profile.nickname.ilike(f"%{search}%"))

    # Sort: online birinchi, keyin last_online vaqti bo'yicha
    # Case expression: online = 0, offline = 1
    online_case = func.case(
        (Profile.last_online >= five_minutes_ago, 0),
        else_=1
    )
    query = query.order_by(online_case, desc(Profile.last_online))

    profiles = query.limit(limit).all()

    players = []
    for p in profiles:
        # Online status
        is_online = p.last_online and p.last_online >= five_minutes_ago

        # Bu o'yinchi bilan aktiv o'yin bormi?
        has_active_match = db.query(Match1v1).filter(
            Match1v1.status.in_([GameStatus.PENDING, GameStatus.ACCEPTED, GameStatus.PLAYING]),
            or_(
                and_(Match1v1.player1_id == current_user.id, Match1v1.player2_id == p.user_id),
                and_(Match1v1.player1_id == p.user_id, Match1v1.player2_id == current_user.id)
            )
        ).first() is not None

        win_rate = round((p.wins / p.total_matches * 100), 1) if p.total_matches > 0 else 0

        players.append({
            "id": str(p.user_id),
            "nickname": p.nickname,
            "avatar_url": p.avatar_url,
            "level": p.level,
            "wins": p.wins,
            "total_matches": p.total_matches,
            "win_rate": win_rate,
            "has_active_match": has_active_match,
            "is_online": is_online,
            "last_online": p.last_online.isoformat() if p.last_online else None
        })

    # Total online count
    total_online = db.query(func.count(Profile.id)).filter(
        Profile.last_online >= five_minutes_ago
    ).scalar() or 0

    return {
        "players": players,
        "count": len(players),
        "total_online": total_online,
        "filter": filter
    }
