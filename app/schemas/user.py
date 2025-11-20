# app/schemas/user.py
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

# Ro'yxatdan o'tish uchun (Client -> Server)
class UserCreate(BaseModel):
    phone_number: str
    password: str

# Javob qaytarish uchun (Server -> Client)
class UserResponse(BaseModel):
    id: UUID
    phone_number: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True