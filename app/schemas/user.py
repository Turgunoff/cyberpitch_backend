# app/schemas/user.py
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional


class ProfileBase(BaseModel):
    nickname: Optional[str] = Field(None, min_length=3, max_length=50)
    pes_id: Optional[str] = Field(None, max_length=50)
    team_strength: Optional[int] = Field(None, ge=0, le=10000)
    avatar_url: Optional[str] = Field(None, max_length=500)
    region: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)


class ProfileUpdate(ProfileBase):
    """Profil yangilash"""
    nickname: Optional[str] = Field(None, min_length=3, max_length=50)
    pes_id: Optional[str] = Field(None, max_length=50)
    team_strength: Optional[int] = Field(None, ge=1000, le=5000)
    region: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)


class ProfileResponse(ProfileBase):
    """Profil javob"""
    id: UUID
    user_id: UUID
    nickname: Optional[str]
    pes_id: Optional[str]
    team_strength: Optional[int]
    avatar_url: Optional[str]
    region: Optional[str]
    bio: Optional[str]
    coins: int
    gems: int
    level: int
    experience: int
    total_matches: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    created_at: datetime

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Hozirgi user ma'lumotlari"""
    id: UUID
    email: str
    is_active: bool
    created_at: datetime
    profile: Optional[ProfileResponse]

    class Config:
        from_attributes = True


class UserPublicResponse(BaseModel):
    """Public user ma'lumotlari (boshqa userlar ko'rishi uchun)"""
    id: UUID
    nickname: Optional[str]
    avatar_url: Optional[str]
    level: int
    total_matches: int
    wins: int
    win_rate: float

    class Config:
        from_attributes = True
