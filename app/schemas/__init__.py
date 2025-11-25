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
    MatchResponse,
    MatchResultSubmit,
    BracketResponse
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
    "MatchResponse",
    "MatchResultSubmit",
    "BracketResponse"
]
