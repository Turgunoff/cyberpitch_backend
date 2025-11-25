# app/schemas/tournament.py
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.models.tournaments import TournamentStatus, TournamentFormat, MatchStatus


# ==================== TOURNAMENT ====================

class TournamentCreate(BaseModel):
    """Turnir yaratish"""
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    format: TournamentFormat = TournamentFormat.SINGLE_ELIMINATION
    max_participants: int = Field(16, ge=4, le=128)
    min_team_strength: int = Field(0, ge=0)
    max_team_strength: int = Field(5000, ge=0)
    entry_fee: int = Field(0, ge=0)
    prize_pool: int = Field(0, ge=0)
    registration_start: Optional[datetime] = None
    registration_end: Optional[datetime] = None
    start_time: Optional[datetime] = None

    @field_validator("max_participants")
    @classmethod
    def validate_participants(cls, v):
        # Power of 2 bo'lishi kerak (bracket uchun)
        if v & (v - 1) != 0:
            raise ValueError("Ishtirokchilar soni 2 ning darajasi bo'lishi kerak (4, 8, 16, 32...)")
        return v

    @field_validator("max_team_strength")
    @classmethod
    def validate_strength(cls, v, info):
        min_strength = info.data.get("min_team_strength", 0)
        if v < min_strength:
            raise ValueError("max_team_strength min_team_strength dan katta bo'lishi kerak")
        return v


class TournamentUpdate(BaseModel):
    """Turnir yangilash"""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    max_participants: Optional[int] = Field(None, ge=4, le=128)
    entry_fee: Optional[int] = Field(None, ge=0)
    prize_pool: Optional[int] = Field(None, ge=0)
    registration_start: Optional[datetime] = None
    registration_end: Optional[datetime] = None
    start_time: Optional[datetime] = None
    status: Optional[TournamentStatus] = None
    is_featured: Optional[bool] = None


class TournamentResponse(BaseModel):
    """Turnir javob"""
    id: UUID
    name: str
    description: Optional[str]
    format: TournamentFormat
    max_participants: int
    min_team_strength: int
    max_team_strength: int
    entry_fee: int
    prize_pool: int
    status: TournamentStatus
    is_featured: bool
    registration_start: Optional[datetime]
    registration_end: Optional[datetime]
    start_time: Optional[datetime]
    participant_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class TournamentListResponse(BaseModel):
    """Turnirlar ro'yxati"""
    tournaments: List[TournamentResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class TournamentDetailResponse(TournamentResponse):
    """Turnir batafsil (ishtirokchilar bilan)"""
    participants: List["ParticipantResponse"] = []
    is_registered: bool = False  # Hozirgi user ro'yxatdan o'tganmi


# ==================== PARTICIPANT ====================

class ParticipantResponse(BaseModel):
    """Ishtirokchi javob"""
    id: UUID
    user_id: UUID
    nickname: Optional[str]
    avatar_url: Optional[str]
    team_strength: Optional[int]
    seed: Optional[int]
    is_checked_in: bool
    is_eliminated: bool
    final_position: Optional[int]
    registered_at: datetime

    class Config:
        from_attributes = True


class JoinTournamentRequest(BaseModel):
    """Turnirga qo'shilish"""
    pass  # Hozircha qo'shimcha ma'lumot kerak emas


# ==================== MATCH ====================

class MatchResponse(BaseModel):
    """Match javob"""
    id: UUID
    tournament_id: UUID
    player1_id: Optional[UUID]
    player2_id: Optional[UUID]
    player1_nickname: Optional[str]
    player2_nickname: Optional[str]
    winner_id: Optional[UUID]
    player1_score: Optional[int]
    player2_score: Optional[int]
    round_number: int
    match_number: int
    status: MatchStatus
    scheduled_time: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class MatchResultSubmit(BaseModel):
    """Match natijasini yuborish"""
    my_score: int = Field(..., ge=0, le=99)
    opponent_score: int = Field(..., ge=0, le=99)
    screenshot_url: Optional[str] = Field(None, max_length=500)


class BracketResponse(BaseModel):
    """Bracket (barcha matchlar)"""
    tournament_id: UUID
    format: TournamentFormat
    total_rounds: int
    matches: List[MatchResponse]


# Circular import hal qilish
TournamentDetailResponse.model_rebuild()
