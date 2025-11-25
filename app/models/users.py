import uuid
from sqlalchemy import Column, String, Boolean, DateTime, func, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    profile = relationship("Profile", back_populates="user", uselist=False)

class Profile(Base):
    __tablename__ = "profiles"

    # --- MANA SHU QATOR TUSHIB QOLGAN EDI ---
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # ----------------------------------------

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    
    # Ma'lumotlar
    nickname = Column(String, unique=True, nullable=True)
    pes_id = Column(String, nullable=True)
    team_strength = Column(Integer, nullable=True)
    avatar_url = Column(String, nullable=True)
    region = Column(String, nullable=True)
    
    # O'yin resurslari
    coins = Column(Integer, default=100)
    gems = Column(Integer, default=0)
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="profile")