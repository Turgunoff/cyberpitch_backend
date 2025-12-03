# app/models/chat.py
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class ChatMessage(Base):
    """O'yinchilar o'rtasidagi xabarlar"""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])

    # Indexes for efficient queries
    __table_args__ = (
        Index('ix_chat_messages_sender_receiver', 'sender_id', 'receiver_id'),
        Index('ix_chat_messages_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<ChatMessage {self.id}>"


class ChatConversation(Base):
    """Suhbat (conversation) - oxirgi xabar keshlanadi"""
    __tablename__ = "chat_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user1_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user2_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    last_message = Column(Text, nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    last_sender_id = Column(UUID(as_uuid=True), nullable=True)

    # User1 uchun o'qilmagan xabarlar soni
    user1_unread = Column(Boolean, default=False)
    # User2 uchun o'qilmagan xabarlar soni
    user2_unread = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])

    __table_args__ = (
        Index('ix_chat_conversations_users', 'user1_id', 'user2_id', unique=True),
    )

    def __repr__(self):
        return f"<ChatConversation {self.id}>"
