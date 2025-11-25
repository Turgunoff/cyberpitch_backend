# app/models/users.py
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # Admin roli
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    created_tournaments = relationship("Tournament", back_populates="creator", foreign_keys="Tournament.created_by")
    tournament_participations = relationship("TournamentParticipant", back_populates="user")

    def __repr__(self):
        return f"<User {self.email}>"


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Asosiy ma'lumotlar
    nickname = Column(String(50), unique=True, nullable=True, index=True)
    pes_id = Column(String(50), nullable=True)
    team_strength = Column(Integer, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    region = Column(String(100), nullable=True)
    bio = Column(String(500), nullable=True)
    
    # O'yin resurslari
    coins = Column(Integer, default=100, nullable=False)
    gems = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    experience = Column(Integer, default=0, nullable=False)
    
    # Statistika
    total_matches = Column(Integer, default=0, nullable=False)
    wins = Column(Integer, default=0, nullable=False)
    losses = Column(Integer, default=0, nullable=False)
    draws = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="profile")

    @property
    def win_rate(self) -> float:
        """Win rate foizda"""
        if self.total_matches == 0:
            return 0.0
        return round((self.wins / self.total_matches) * 100, 2)

    def __repr__(self):
        return f"<Profile {self.nickname}>"
