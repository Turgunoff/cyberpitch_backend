# app/models/tournaments.py
import uuid
import enum
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Text, Boolean, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


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
    format = Column(Enum(TournamentFormat), default=TournamentFormat.SINGLE_ELIMINATION, nullable=False)
    max_participants = Column(Integer, default=16, nullable=False)
    min_team_strength = Column(Integer, default=0, nullable=False)
    max_team_strength = Column(Integer, default=5000, nullable=False)
    entry_fee = Column(Integer, default=0, nullable=False)
    prize_pool = Column(Integer, default=0, nullable=False)
    
    # Vaqtlar
    registration_start = Column(DateTime(timezone=True), nullable=True)
    registration_end = Column(DateTime(timezone=True), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Holat
    status = Column(Enum(TournamentStatus), default=TournamentStatus.UPCOMING, nullable=False, index=True)
    is_featured = Column(Boolean, default=False, index=True)
    
    # Yaratuvchi
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    creator = relationship("User", back_populates="created_tournaments", foreign_keys=[created_by])
    participants = relationship("TournamentParticipant", back_populates="tournament", cascade="all, delete-orphan")
    matches = relationship("Match", back_populates="tournament", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_tournaments_status_start_time", "status", "start_time"),
    )

    def __repr__(self):
        return f"<Tournament {self.name}>"


class TournamentParticipant(Base):
    __tablename__ = "tournament_participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tournament_id = Column(UUID(as_uuid=True), ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    seed = Column(Integer, nullable=True)
    is_checked_in = Column(Boolean, default=False, nullable=False)
    is_eliminated = Column(Boolean, default=False, nullable=False)
    final_position = Column(Integer, nullable=True)  # Yakuniy o'rin
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tournament = relationship("Tournament", back_populates="participants")
    user = relationship("User", back_populates="tournament_participations")

    # Bir user bir turnirga faqat bir marta qatnasha oladi
    __table_args__ = (
        UniqueConstraint("tournament_id", "user_id", name="uq_tournament_user"),
        Index("ix_participant_tournament", "tournament_id"),
    )

    def __repr__(self):
        return f"<Participant tournament={self.tournament_id} user={self.user_id}>"


class Match(Base):
    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tournament_id = Column(UUID(as_uuid=True), ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    
    # O'yinchilar
    player1_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    player2_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    winner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Natijalar
    player1_score = Column(Integer, nullable=True)
    player2_score = Column(Integer, nullable=True)
    
    # Bracket info
    round_number = Column(Integer, default=1, nullable=False)
    match_number = Column(Integer, default=1, nullable=False)
    next_match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id", ondelete="SET NULL"), nullable=True)
    bracket_position = Column(String(20), nullable=True)  # "upper", "lower", "final"
    
    # Holat
    status = Column(Enum(MatchStatus), default=MatchStatus.PENDING, nullable=False, index=True)
    scheduled_time = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Screenshots (natija tasdiqlash uchun)
    player1_screenshot = Column(String(500), nullable=True)
    player2_screenshot = Column(String(500), nullable=True)
    
    # Dispute
    dispute_reason = Column(Text, nullable=True)
    dispute_resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    tournament = relationship("Tournament", back_populates="matches")
    player1 = relationship("User", foreign_keys=[player1_id], backref="matches_as_player1")
    player2 = relationship("User", foreign_keys=[player2_id], backref="matches_as_player2")
    winner = relationship("User", foreign_keys=[winner_id])
    next_match = relationship("Match", remote_side=[id], backref="previous_matches")

    # Indexes
    __table_args__ = (
        Index("ix_match_tournament_round", "tournament_id", "round_number"),
        Index("ix_match_players", "player1_id", "player2_id"),
    )

    def __repr__(self):
        return f"<Match {self.id} round={self.round_number}>"
