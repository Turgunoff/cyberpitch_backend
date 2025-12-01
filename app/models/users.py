# app/models/users.py
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
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
    
    # ══════════════════════════════════════════════════════════
    # SHAXSIY MA'LUMOTLAR
    # ══════════════════════════════════════════════════════════
    nickname = Column(String(50), unique=True, nullable=True, index=True)
    full_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    birth_date = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)  # male, female, other
    avatar_url = Column(String(500), nullable=True)
    region = Column(String(100), nullable=True)
    bio = Column(String(500), nullable=True)
    language = Column(String(10), default='uz')  # uz, ru, en
    
    # ══════════════════════════════════════════════════════════
    # IJTIMOIY TARMOQLAR
    # ══════════════════════════════════════════════════════════
    telegram = Column(String(50), nullable=True)      # @username
    instagram = Column(String(50), nullable=True)     # @username
    youtube = Column(String(100), nullable=True)      # channel URL
    discord = Column(String(50), nullable=True)       # username#1234
    
    # ══════════════════════════════════════════════════════════
    # O'YIN MA'LUMOTLARI
    # ══════════════════════════════════════════════════════════
    pes_id = Column(String(50), nullable=True)
    team_strength = Column(Integer, nullable=True)
    favorite_team = Column(String(50), nullable=True)       # Barcelona, Real Madrid
    play_style = Column(String(20), nullable=True)          # attacking, defensive, balanced
    preferred_formation = Column(String(10), nullable=True) # 4-3-3, 4-2-4
    available_hours = Column(String(50), nullable=True)     # "18:00-23:00"
    
    # ══════════════════════════════════════════════════════════
    # RESURSLAR
    # ══════════════════════════════════════════════════════════
    coins = Column(Integer, default=100, nullable=False)
    gems = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    experience = Column(Integer, default=0, nullable=False)
    
    # ══════════════════════════════════════════════════════════
    # STATISTIKA
    # ══════════════════════════════════════════════════════════
    total_matches = Column(Integer, default=0, nullable=False)
    wins = Column(Integer, default=0, nullable=False)
    losses = Column(Integer, default=0, nullable=False)
    draws = Column(Integer, default=0, nullable=False)
    tournaments_won = Column(Integer, default=0, nullable=False)
    tournaments_played = Column(Integer, default=0, nullable=False)
    
    # ══════════════════════════════════════════════════════════
    # STATUS VA SOZLAMALAR
    # ══════════════════════════════════════════════════════════
    is_verified = Column(Boolean, default=False)      # Tasdiqlangan profil
    is_pro = Column(Boolean, default=False)           # Professional o'yinchi
    is_public = Column(Boolean, default=True)         # Profil ochiqmi
    show_stats = Column(Boolean, default=True)        # Statistika ko'rsatilsinmi
    last_online = Column(DateTime(timezone=True), nullable=True)
    
    # ══════════════════════════════════════════════════════════
    # TIMESTAMPS
    # ══════════════════════════════════════════════════════════
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
    
    @property
    def age(self) -> int | None:
        """Yoshni hisoblash"""
        if not self.birth_date:
            return None
        from datetime import date
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    def __repr__(self):
        return f"<Profile {self.nickname}>"


class Friendship(Base):
    """Do'stlik tizimi"""
    __tablename__ = "friendships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # So'rov yuboruvchi
    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # So'rov qabul qiluvchi
    addressee_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Status: pending, accepted, declined, blocked
    status = Column(String(20), default="pending", nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    requester = relationship("User", foreign_keys=[requester_id])
    addressee = relationship("User", foreign_keys=[addressee_id])