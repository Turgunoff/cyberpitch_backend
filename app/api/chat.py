# app/api/chat.py
"""
Chat API - O'yinchilar o'rtasida xabar almashish
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from uuid import UUID
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.users import User, Profile
from app.models.chat import ChatMessage, ChatConversation
from app.schemas.chat import (
    MessageCreate,
    MessageResponse,
    ConversationResponse,
    ConversationsListResponse,
    MessagesListResponse,
)

router = APIRouter()


# ══════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_or_create_conversation(db: Session, user1_id: UUID, user2_id: UUID) -> ChatConversation:
    """Suhbatni olish yoki yaratish"""
    # IDs ni tartibda saqlash (user1_id < user2_id)
    if str(user1_id) > str(user2_id):
        user1_id, user2_id = user2_id, user1_id

    conversation = db.query(ChatConversation).filter(
        ChatConversation.user1_id == user1_id,
        ChatConversation.user2_id == user2_id
    ).first()

    if not conversation:
        conversation = ChatConversation(
            user1_id=user1_id,
            user2_id=user2_id
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    return conversation


def get_user_profile(db: Session, user_id: UUID) -> dict:
    """User profil ma'lumotlarini olish"""
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    return {
        "nickname": profile.nickname if profile else "Unknown",
        "avatar_url": profile.avatar_url if profile else None
    }


# ══════════════════════════════════════════════════════════
# CONVERSATIONS
# ══════════════════════════════════════════════════════════

@router.get("/conversations", summary="Suhbatlar ro'yxati")
def get_conversations(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ConversationsListResponse:
    """Foydalanuvchining barcha suhbatlari"""
    user_id = current_user.id

    # Total count
    total = db.query(ChatConversation).filter(
        or_(
            ChatConversation.user1_id == user_id,
            ChatConversation.user2_id == user_id
        )
    ).count()

    # Conversations with last message
    conversations = db.query(ChatConversation).filter(
        or_(
            ChatConversation.user1_id == user_id,
            ChatConversation.user2_id == user_id
        )
    ).order_by(
        desc(ChatConversation.last_message_at)
    ).offset(offset).limit(limit).all()

    result = []
    for conv in conversations:
        # Boshqa foydalanuvchini aniqlash
        other_user_id = conv.user2_id if conv.user1_id == user_id else conv.user1_id
        other_profile = get_user_profile(db, other_user_id)

        # O'qilmagan xabar bormi?
        has_unread = False
        if conv.user1_id == user_id:
            has_unread = conv.user1_unread
        else:
            has_unread = conv.user2_unread

        result.append(ConversationResponse(
            id=conv.id,
            other_user_id=other_user_id,
            other_user_nickname=other_profile["nickname"],
            other_user_avatar=other_profile["avatar_url"],
            last_message=conv.last_message,
            last_message_at=conv.last_message_at,
            has_unread=has_unread
        ))

    return ConversationsListResponse(conversations=result, total=total)


# ══════════════════════════════════════════════════════════
# MESSAGES
# ══════════════════════════════════════════════════════════

@router.get("/messages/{user_id}", summary="Foydalanuvchi bilan xabarlar")
def get_messages(
    user_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    before: datetime = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> MessagesListResponse:
    """Muayyan foydalanuvchi bilan bo'lgan xabarlar"""
    my_id = current_user.id

    # User mavjudligini tekshirish
    other_user = db.query(User).filter(User.id == user_id).first()
    if not other_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foydalanuvchi topilmadi"
        )

    # Xabarlar query
    query = db.query(ChatMessage).filter(
        or_(
            and_(ChatMessage.sender_id == my_id, ChatMessage.receiver_id == user_id),
            and_(ChatMessage.sender_id == user_id, ChatMessage.receiver_id == my_id)
        )
    )

    # Pagination by date
    if before:
        query = query.filter(ChatMessage.created_at < before)

    # Total count
    total = query.count()

    # Get messages (newest first)
    messages = query.order_by(desc(ChatMessage.created_at)).limit(limit + 1).all()

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    # Xabarlarni o'qilgan deb belgilash
    db.query(ChatMessage).filter(
        ChatMessage.sender_id == user_id,
        ChatMessage.receiver_id == my_id,
        ChatMessage.is_read == False
    ).update({ChatMessage.is_read: True})

    # Conversation'ni yangilash
    conversation = get_or_create_conversation(db, my_id, user_id)
    if conversation.user1_id == my_id:
        conversation.user1_unread = False
    else:
        conversation.user2_unread = False

    db.commit()

    # Response
    result = []
    for msg in reversed(messages):  # Oldest first for display
        sender_profile = get_user_profile(db, msg.sender_id)
        result.append(MessageResponse(
            id=msg.id,
            sender_id=msg.sender_id,
            receiver_id=msg.receiver_id,
            content=msg.content,
            is_read=msg.is_read,
            created_at=msg.created_at,
            sender_nickname=sender_profile["nickname"],
            sender_avatar=sender_profile["avatar_url"]
        ))

    return MessagesListResponse(messages=result, total=total, has_more=has_more)


@router.post("/messages", summary="Xabar yuborish")
def send_message(
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> MessageResponse:
    """Yangi xabar yuborish"""
    my_id = current_user.id
    receiver_id = data.receiver_id

    # O'ziga xabar yuborish mumkin emas
    if my_id == receiver_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O'zingizga xabar yubora olmaysiz"
        )

    # Receiver mavjudligini tekshirish
    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foydalanuvchi topilmadi"
        )

    # Xabar yaratish
    message = ChatMessage(
        sender_id=my_id,
        receiver_id=receiver_id,
        content=data.content.strip()
    )
    db.add(message)

    # Conversation'ni yangilash
    conversation = get_or_create_conversation(db, my_id, receiver_id)
    conversation.last_message = data.content[:100]  # Truncate
    conversation.last_message_at = datetime.now(timezone.utc)
    conversation.last_sender_id = my_id

    # Receiver uchun unread flag
    if conversation.user1_id == receiver_id:
        conversation.user1_unread = True
    else:
        conversation.user2_unread = True

    db.commit()
    db.refresh(message)

    # Sender profile
    sender_profile = get_user_profile(db, my_id)

    return MessageResponse(
        id=message.id,
        sender_id=message.sender_id,
        receiver_id=message.receiver_id,
        content=message.content,
        is_read=message.is_read,
        created_at=message.created_at,
        sender_nickname=sender_profile["nickname"],
        sender_avatar=sender_profile["avatar_url"]
    )


@router.get("/unread-count", summary="O'qilmagan xabarlar soni")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    """O'qilmagan xabarlar soni"""
    count = db.query(ChatConversation).filter(
        or_(
            and_(ChatConversation.user1_id == current_user.id, ChatConversation.user1_unread == True),
            and_(ChatConversation.user2_id == current_user.id, ChatConversation.user2_unread == True)
        )
    ).count()

    return {"unread_count": count}
