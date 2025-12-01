# app/schemas/match.py
"""
1vs1 o'yinlar uchun schemalar
"""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.models.matches import GameMode, GameStatus


# ══════════════════════════════════════════════════════════
# MATCH CREATE / UPDATE
# ══════════════════════════════════════════════════════════

class MatchCreate(BaseModel):
    """1vs1 o'yin yaratish (challenge yuborish)"""
    opponent_id: UUID
    mode: GameMode = GameMode.RANKED
    bet_amount: int = Field(0, ge=0, description="Tikish summasi (faqat challenge mode)")


class MatchResultSubmit(BaseModel):
    """O'yin natijasini yuborish"""
    my_score: int = Field(..., ge=0, le=99)
    opponent_score: int = Field(..., ge=0, le=99)
    screenshot_url: Optional[str] = Field(None, max_length=500)


# ══════════════════════════════════════════════════════════
# MATCH RESPONSE
# ══════════════════════════════════════════════════════════

class MatchOpponentInfo(BaseModel):
    """Opponent ma'lumotlari"""
    id: UUID
    nickname: Optional[str]
    avatar_url: Optional[str]
    team_strength: Optional[int]


class MatchResponse(BaseModel):
    """Bitta o'yin"""
    id: UUID
    mode: GameMode
    status: GameStatus

    # O'yinchilar
    player1_id: UUID
    player2_id: UUID
    winner_id: Optional[UUID]

    # Natija
    player1_score: Optional[int]
    player2_score: Optional[int]
    score_display: str

    # Reyting o'zgarishi
    player1_rating_change: int
    player2_rating_change: int

    # Bet
    bet_amount: int

    # Vaqtlar
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class MatchHistoryItem(BaseModel):
    """O'yin tarixi ro'yxatidagi element"""
    id: UUID
    mode: GameMode
    status: GameStatus

    # Opponent (hozirgi user nuqtai nazaridan)
    opponent: MatchOpponentInfo

    # Natija
    score: str              # "3-1"
    result: str             # "WIN", "LOSS", "DRAW"
    rating_change: int      # +28 yoki -22

    # Vaqt
    played_at: datetime


class MatchHistoryResponse(BaseModel):
    """O'yin tarixi ro'yxati"""
    matches: List[MatchHistoryItem]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


# ══════════════════════════════════════════════════════════
# USER STATS
# ══════════════════════════════════════════════════════════

class UserMatchStats(BaseModel):
    """Foydalanuvchi o'yin statistikasi"""
    total_matches: int
    wins: int
    losses: int
    draws: int
    win_rate: float

    # Goals
    goals_scored: int
    goals_conceded: int
    avg_goals_per_match: float
    clean_sheets: int

    # Streaks
    current_streak: int      # Hozirgi streak (musbat = win, manfiy = loss)
    longest_win_streak: int
    longest_loss_streak: int

    # Ranked stats
    ranked_matches: int
    ranked_wins: int
    ranked_rating: int       # ELO rating

    # Tournament stats
    tournaments_played: int
    tournaments_won: int
    best_tournament_position: Optional[int]
    total_tournament_earnings: int


class UserStatsResponse(BaseModel):
    """Foydalanuvchi to'liq statistikasi"""
    overview: UserMatchStats
    recent_form: List[str]   # ["W", "W", "L", "W", "D"] - oxirgi 5 ta o'yin
    monthly_stats: dict      # Oylik statistika
