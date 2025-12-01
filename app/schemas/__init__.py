# app/schemas/__init__.py
from .auth import EmailLoginRequest, VerifyOTPRequest, TokenResponse, RefreshTokenRequest
from .user import ProfileResponse, ProfileUpdate, UserResponse
from .tournament import (
    TournamentCreate,
    TournamentUpdate,
    TournamentResponse,
    TournamentListResponse,
    TournamentDetailResponse,
    ParticipantResponse,
    MatchResponse as TournamentMatchResponse,
    MatchResultSubmit as TournamentMatchResultSubmit,
    BracketResponse
)
from .match import (
    MatchCreate,
    MatchResultSubmit,
    MatchResponse,
    MatchHistoryItem,
    MatchHistoryResponse,
    UserMatchStats,
    UserStatsResponse
)

__all__ = [
    # Auth
    "EmailLoginRequest",
    "VerifyOTPRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    # User
    "ProfileResponse",
    "ProfileUpdate",
    "UserResponse",
    # Tournament
    "TournamentCreate",
    "TournamentUpdate",
    "TournamentResponse",
    "TournamentListResponse",
    "TournamentDetailResponse",
    "ParticipantResponse",
    "TournamentMatchResponse",
    "TournamentMatchResultSubmit",
    "BracketResponse",
    # 1v1 Match
    "MatchCreate",
    "MatchResultSubmit",
    "MatchResponse",
    "MatchHistoryItem",
    "MatchHistoryResponse",
    "UserMatchStats",
    "UserStatsResponse",
]
