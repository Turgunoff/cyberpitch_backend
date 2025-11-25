from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.models.tournaments import TournamentStatus, TournamentFormat

# Create
class TournamentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    format: TournamentFormat = TournamentFormat.SINGLE_ELIMINATION
    max_participants: int = 16
    min_team_strength: int = 0
    max_team_strength: int = 5000
    entry_fee: int = 0
    prize_pool: int = 0
    registration_start: Optional[datetime] = None
    registration_end: Optional[datetime] = None
    start_time: Optional[datetime] = None

# Response
class TournamentResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    format: TournamentFormat
    max_participants: int
    entry_fee: int
    prize_pool: int
    status: TournamentStatus
    is_featured: bool
    start_time: Optional[datetime]
    participant_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True

# List
class TournamentListResponse(BaseModel):
    tournaments: List[TournamentResponse]
    total: int
    page: int
    per_page: int

# Join
class JoinTournamentRequest(BaseModel):
    tournament_id: UUID

# Match Result
class MatchResultSubmit(BaseModel):
    match_id: UUID
    my_score: int
    opponent_score: int
    screenshot_url: Optional[str] = None