# app/models/matches.py
"""
1vs1 o'yinlar uchun model
Turnirlardan tashqari individual o'yinlar (ranked, friendly, challenge)
"""

import uuid
import enum
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class GameMode(str, enum.Enum):
    """O'yin turi"""
    RANKED = "ranked"        # Reytingga ta'sir qiladi
    FRIENDLY = "friendly"    # Do'stona o'yin
    CHALLENGE = "challenge"  # Challenge (pul tikish bilan)


class GameResult(str, enum.Enum):
    """O'yin natijasi"""
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"


class GameStatus(str, enum.Enum):
    """O'yin holati"""
    PENDING = "pending"          # Kutilmoqda (opponent qabul qilishi kerak)
    ACCEPTED = "accepted"        # Qabul qilindi, o'yin boshlanmagan
    PLAYING = "playing"          # O'yin davom etmoqda
    RESULT_SUBMITTED = "result_submitted"  # Natija yuborildi
    COMPLETED = "completed"      # Yakunlangan
    CANCELLED = "cancelled"      # Bekor qilingan
    DISPUTED = "disputed"        # Nizo (natijalar mos kelmasa)


class Match1v1(Base):
    """
    1vs1 individual o'yinlar
    Turnirdan tashqari ranked/friendly/challenge o'yinlar
    """
    __tablename__ = "matches_1v1"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ══════════════════════════════════════════════════════════
    # O'YINCHILAR
    # ══════════════════════════════════════════════════════════
    player1_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    player2_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    winner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # ══════════════════════════════════════════════════════════
    # NATIJA
    # ══════════════════════════════════════════════════════════
    player1_score = Column(Integer, nullable=True)
    player2_score = Column(Integer, nullable=True)

    # ══════════════════════════════════════════════════════════
    # O'YIN TURI VA HOLAT
    # ══════════════════════════════════════════════════════════
    mode = Column(Enum(GameMode), default=GameMode.RANKED, nullable=False, index=True)
    status = Column(Enum(GameStatus), default=GameStatus.PENDING, nullable=False, index=True)

    # ══════════════════════════════════════════════════════════
    # REYTING O'ZGARISHI
    # ══════════════════════════════════════════════════════════
    player1_rating_change = Column(Integer, default=0)  # +28 yoki -22
    player2_rating_change = Column(Integer, default=0)

    # ══════════════════════════════════════════════════════════
    # CHALLENGE (pul tikish)
    # ══════════════════════════════════════════════════════════
    bet_amount = Column(Integer, default=0)  # Tikish summasi (coins)

    # ══════════════════════════════════════════════════════════
    # SCREENSHOT (natija tasdiqlash)
    # ══════════════════════════════════════════════════════════
    player1_screenshot = Column(String(500), nullable=True)
    player2_screenshot = Column(String(500), nullable=True)

    # ══════════════════════════════════════════════════════════
    # QOSHIMCHA MA'LUMOTLAR
    # ══════════════════════════════════════════════════════════
    # Player1 natijani birinchi yubordi
    player1_submitted = Column(Boolean, default=False)
    player2_submitted = Column(Boolean, default=False)

    # Natijalar (player tomonidan yuborilgan)
    player1_claimed_score = Column(String(10), nullable=True)  # "3-1" formatda
    player2_claimed_score = Column(String(10), nullable=True)

    # Dispute
    dispute_reason = Column(Text, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # ══════════════════════════════════════════════════════════
    # VAQTLAR
    # ══════════════════════════════════════════════════════════
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # ══════════════════════════════════════════════════════════
    # RELATIONSHIPS
    # ══════════════════════════════════════════════════════════
    player1 = relationship("User", foreign_keys=[player1_id], backref="matches_as_p1")
    player2 = relationship("User", foreign_keys=[player2_id], backref="matches_as_p2")
    winner = relationship("User", foreign_keys=[winner_id])
    resolver = relationship("User", foreign_keys=[resolved_by])

    # ══════════════════════════════════════════════════════════
    # INDEXES
    # ══════════════════════════════════════════════════════════
    __table_args__ = (
        Index("ix_match_players_created", "player1_id", "player2_id", "created_at"),
        Index("ix_match_status_mode", "status", "mode"),
    )

    def __repr__(self):
        return f"<Match1v1 {self.id} {self.player1_id} vs {self.player2_id}>"

    @property
    def score_display(self) -> str:
        """Natijani ko'rsatish uchun"""
        if self.player1_score is None or self.player2_score is None:
            return "-"
        return f"{self.player1_score}-{self.player2_score}"
