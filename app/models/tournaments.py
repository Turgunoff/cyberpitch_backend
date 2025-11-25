import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class TournamentStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    REGISTRATION = "registration"
    LIVE = "live"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TournamentFormat(str, enum.Enum):
    SINGLE_ELIMINATION = "single_elimination"
    DOUBLE_ELIMINATION = "double_elimination"
    ROUND_ROBIN = "round_robin"
    SWISS = "swiss"

class MatchStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    PLAYING = "playing"
    DISPUTED = "disputed"
    COMPLETED = "completed"

class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Turnir sozlamalari
    format = Column(Enum(TournamentFormat), default=TournamentFormat.SINGLE_ELIMINATION)
    max_participants = Column(Integer, default=16)
    min_team_strength = Column(Integer, default=0)
    max_team_strength = Column(Integer, default=5000)
    entry_fee = Column(Integer, default=0)  # Coins
    prize_pool = Column(Integer, default=0)
    
    # Vaqtlar
    registration_start = Column(DateTime(timezone=True), nullable=True)
    registration_end = Column(DateTime(timezone=True), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    
    # Holat
    status = Column(Enum(TournamentStatus), default=TournamentStatus.UPCOMING)
    is_featured = Column(Boolean, default=False)
    
    # Yaratuvchi
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    participants = relationship("TournamentParticipant", back_populates="tournament")
    matches = relationship("Match", back_populates="tournament")

class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tournament_id = Column(UUID(as_uuid=True), ForeignKey("tournaments.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    seed = Column(Integer, nullable=True)  # Turnirdagi o'rni
    is_checked_in = Column(Boolean, default=False)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tournament = relationship("Tournament", back_populates="participants")
    user = relationship("User")

class Match(Base):
    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tournament_id = Column(UUID(as_uuid=True), ForeignKey("tournaments.id"), nullable=False)
    
    # O'yinchilar
    player1_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    player2_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    winner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Natijalar
    player1_score = Column(Integer, nullable=True)
    player2_score = Column(Integer, nullable=True)
    
    # Bracket info
    round_number = Column(Integer, default=1)
    match_number = Column(Integer, default=1)
    next_match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id"), nullable=True)
    
    # Holat
    status = Column(Enum(MatchStatus), default=MatchStatus.PENDING)
    scheduled_time = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Screenshots
    player1_screenshot = Column(String(500), nullable=True)
    player2_screenshot = Column(String(500), nullable=True)

    # Relationships
    tournament = relationship("Tournament", back_populates="matches")
    player1 = relationship("User", foreign_keys=[player1_id])
    player2 = relationship("User", foreign_keys=[player2_id])
    winner = relationship("User", foreign_keys=[winner_id])