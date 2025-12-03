# app/api/websocket.py
"""
WebSocket API - Real-time xabarlar
- Online status tracking
- Challenge events (yangi challenge, qabul/rad)
- Match events (score update, game end)
- Matchmaking events
"""

import logging
import json
from typing import Dict, Set, Optional
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.users import User, Profile

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket ulanishlarni boshqarish"""

    def __init__(self):
        # user_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # user_id -> Set[room_id] (masalan: match_id, tournament_id)
        self.user_rooms: Dict[str, Set[str]] = {}
        # room_id -> Set[user_id]
        self.rooms: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Yangi ulanish qo'shish"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.user_rooms[user_id] = set()
        logger.info(f"🔌 WebSocket connected: {user_id[:8]}... (Total: {len(self.active_connections)})")

    def disconnect(self, user_id: str):
        """Ulanishni o'chirish"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]

        # User ni barcha roomlardan chiqarish
        if user_id in self.user_rooms:
            for room_id in self.user_rooms[user_id]:
                if room_id in self.rooms:
                    self.rooms[room_id].discard(user_id)
            del self.user_rooms[user_id]

        logger.info(f"🔌 WebSocket disconnected: {user_id[:8]}... (Total: {len(self.active_connections)})")

    def is_online(self, user_id: str) -> bool:
        """User online ekanligini tekshirish"""
        return user_id in self.active_connections

    def get_online_users(self) -> list:
        """Online userlar ro'yxati"""
        return list(self.active_connections.keys())

    def get_online_count(self) -> int:
        """Online userlar soni"""
        return len(self.active_connections)

    async def send_personal(self, user_id: str, message: dict):
        """Bitta userga xabar yuborish"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
                return True
            except Exception as e:
                logger.error(f"WebSocket send error: {e}")
                self.disconnect(user_id)
        return False

    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        """Barcha userlarga xabar yuborish"""
        disconnected = []
        for user_id, connection in self.active_connections.items():
            if user_id != exclude:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(user_id)

        # Uzilgan ulanishlarni tozalash
        for user_id in disconnected:
            self.disconnect(user_id)

    # ══════════════════════════════════════════════════════════
    # ROOM MANAGEMENT (Match, Tournament uchun)
    # ══════════════════════════════════════════════════════════

    def join_room(self, user_id: str, room_id: str):
        """Userini roomga qo'shish"""
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(user_id)

        if user_id in self.user_rooms:
            self.user_rooms[user_id].add(room_id)

        logger.info(f"👥 User {user_id[:8]}... joined room {room_id[:8]}...")

    def leave_room(self, user_id: str, room_id: str):
        """Userni roomdan chiqarish"""
        if room_id in self.rooms:
            self.rooms[room_id].discard(user_id)
            if not self.rooms[room_id]:
                del self.rooms[room_id]

        if user_id in self.user_rooms:
            self.user_rooms[user_id].discard(room_id)

    async def send_to_room(self, room_id: str, message: dict, exclude: Optional[str] = None):
        """Room ichidagi barcha userlarga xabar"""
        if room_id not in self.rooms:
            return

        disconnected = []
        for user_id in self.rooms[room_id]:
            if user_id != exclude and user_id in self.active_connections:
                try:
                    await self.active_connections[user_id].send_json(message)
                except Exception:
                    disconnected.append(user_id)

        for user_id in disconnected:
            self.disconnect(user_id)


# Global manager
manager = ConnectionManager()


def get_user_from_token(token: str, db: Session) -> Optional[User]:
    """Token dan user olish"""
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket endpoint

    Query params:
        token: JWT access token

    Messages format:
        {
            "type": "event_type",
            "data": {...}
        }

    Event types:
        - ping/pong: Heartbeat
        - join_room: Room ga qo'shilish
        - leave_room: Room dan chiqish
        - challenge_response: Challenge javob
        - score_update: O'yin score yangilash
    """
    # Database session
    from app.core.database import SessionLocal
    db = SessionLocal()

    try:
        # Token tekshirish
        user = get_user_from_token(token, db)
        if not user:
            await websocket.close(code=4001, reason="Invalid token")
            return

        user_id = str(user.id)

        # Ulanishni qo'shish
        await manager.connect(websocket, user_id)

        # Online status yangilash
        if user.profile:
            user.profile.last_online = datetime.now(timezone.utc)
            db.commit()

        # Online users sonini broadcast qilish
        await manager.broadcast({
            "type": "online_count",
            "data": {"count": manager.get_online_count()}
        })

        try:
            while True:
                # Xabar kutish
                data = await websocket.receive_json()
                event_type = data.get("type")
                event_data = data.get("data", {})

                # ═══════════════════════════════════════
                # HEARTBEAT
                # ═══════════════════════════════════════
                if event_type == "ping":
                    await manager.send_personal(user_id, {
                        "type": "pong",
                        "data": {"timestamp": datetime.now(timezone.utc).isoformat()}
                    })

                    # Online status yangilash
                    if user.profile:
                        user.profile.last_online = datetime.now(timezone.utc)
                        db.commit()

                # ═══════════════════════════════════════
                # ROOM MANAGEMENT
                # ═══════════════════════════════════════
                elif event_type == "join_room":
                    room_id = event_data.get("room_id")
                    if room_id:
                        manager.join_room(user_id, room_id)
                        await manager.send_personal(user_id, {
                            "type": "room_joined",
                            "data": {"room_id": room_id}
                        })

                elif event_type == "leave_room":
                    room_id = event_data.get("room_id")
                    if room_id:
                        manager.leave_room(user_id, room_id)
                        await manager.send_personal(user_id, {
                            "type": "room_left",
                            "data": {"room_id": room_id}
                        })

                # ═══════════════════════════════════════
                # CHALLENGE RESPONSE
                # ═══════════════════════════════════════
                elif event_type == "challenge_accepted":
                    match_id = event_data.get("match_id")
                    challenger_id = event_data.get("challenger_id")

                    if challenger_id:
                        nickname = user.profile.nickname if user.profile else "O'yinchi"
                        await manager.send_personal(challenger_id, {
                            "type": "challenge_accepted",
                            "data": {
                                "match_id": match_id,
                                "opponent_id": user_id,
                                "opponent_name": nickname
                            }
                        })

                elif event_type == "challenge_declined":
                    match_id = event_data.get("match_id")
                    challenger_id = event_data.get("challenger_id")

                    if challenger_id:
                        nickname = user.profile.nickname if user.profile else "O'yinchi"
                        await manager.send_personal(challenger_id, {
                            "type": "challenge_declined",
                            "data": {
                                "match_id": match_id,
                                "opponent_id": user_id,
                                "opponent_name": nickname
                            }
                        })

                # ═══════════════════════════════════════
                # SCORE UPDATE (Match davomida)
                # ═══════════════════════════════════════
                elif event_type == "score_update":
                    match_id = event_data.get("match_id")
                    my_score = event_data.get("my_score")
                    opponent_score = event_data.get("opponent_score")

                    if match_id:
                        # Room ichidagi barcha userlarga yuborish
                        await manager.send_to_room(match_id, {
                            "type": "score_updated",
                            "data": {
                                "match_id": match_id,
                                "user_id": user_id,
                                "my_score": my_score,
                                "opponent_score": opponent_score,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        }, exclude=user_id)

                # ═══════════════════════════════════════
                # GET ONLINE STATUS
                # ═══════════════════════════════════════
                elif event_type == "get_online_status":
                    user_ids = event_data.get("user_ids", [])
                    online_status = {
                        uid: manager.is_online(uid)
                        for uid in user_ids
                    }
                    await manager.send_personal(user_id, {
                        "type": "online_status",
                        "data": online_status
                    })

                # ═══════════════════════════════════════
                # TYPING INDICATOR (Chat uchun)
                # ═══════════════════════════════════════
                elif event_type == "typing":
                    target_user_id = event_data.get("to_user_id")
                    if target_user_id:
                        await manager.send_personal(target_user_id, {
                            "type": "user_typing",
                            "data": {
                                "user_id": user_id,
                                "is_typing": event_data.get("is_typing", True)
                            }
                        })

        except WebSocketDisconnect:
            pass

    finally:
        # Ulanish uzilganda
        if 'user_id' in dir():
            manager.disconnect(user_id)

            # Online count yangilash
            await manager.broadcast({
                "type": "online_count",
                "data": {"count": manager.get_online_count()}
            })

        db.close()


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (Boshqa modullardan chaqirish uchun)
# ══════════════════════════════════════════════════════════════════

async def notify_user(user_id: str, event_type: str, data: dict):
    """
    Userga WebSocket orqali xabar yuborish

    Usage:
        from app.api.websocket import notify_user
        await notify_user(user_id, "new_challenge", {"match_id": "..."})
    """
    return await manager.send_personal(user_id, {
        "type": event_type,
        "data": data
    })


async def notify_room(room_id: str, event_type: str, data: dict, exclude: Optional[str] = None):
    """Room ga xabar yuborish"""
    return await manager.send_to_room(room_id, {
        "type": event_type,
        "data": data
    }, exclude=exclude)


async def broadcast_event(event_type: str, data: dict, exclude: Optional[str] = None):
    """Barcha online userlarga xabar"""
    return await manager.broadcast({
        "type": event_type,
        "data": data
    }, exclude=exclude)


def is_user_online(user_id: str) -> bool:
    """User online ekanligini tekshirish"""
    return manager.is_online(user_id)


def get_online_count() -> int:
    """Online userlar soni"""
    return manager.get_online_count()
