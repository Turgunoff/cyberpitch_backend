# app/schemas/chat.py
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class MessageCreate(BaseModel):
    """Yangi xabar yuborish"""
    receiver_id: UUID
    content: str = Field(..., min_length=1, max_length=2000)


class MessageResponse(BaseModel):
    """Xabar response"""
    id: UUID
    sender_id: UUID
    receiver_id: UUID
    content: str
    is_read: bool
    created_at: datetime

    # Sender info
    sender_nickname: Optional[str] = None
    sender_avatar: Optional[str] = None

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Suhbat (conversation) response"""
    id: UUID
    other_user_id: UUID
    other_user_nickname: str
    other_user_avatar: Optional[str] = None
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    has_unread: bool = False

    class Config:
        from_attributes = True


class ConversationsListResponse(BaseModel):
    """Barcha suhbatlar ro'yxati"""
    conversations: List[ConversationResponse]
    total: int


class MessagesListResponse(BaseModel):
    """Suhbat xabarlari"""
    messages: List[MessageResponse]
    total: int
    has_more: bool


class MarkReadRequest(BaseModel):
    """Xabarlarni o'qilgan deb belgilash"""
    conversation_id: UUID
