# app/services/notification_service.py
import httpx
import logging
from typing import Optional, List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """OneSignal orqali push notification yuborish"""

    BASE_URL = "https://onesignal.com/api/v1/notifications"

    @classmethod
    def _get_headers(cls) -> dict:
        return {
            "Authorization": f"Basic {settings.ONESIGNAL_REST_API_KEY}",
            "Content-Type": "application/json",
        }

    @classmethod
    async def send_to_player(
        cls,
        player_id: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        sound: Optional[str] = None,
    ) -> bool:
        """
        Bitta o'yinchiga notification yuborish

        Args:
            player_id: OneSignal Player ID
            title: Notification sarlavhasi
            message: Notification matni
            data: Qo'shimcha ma'lumotlar (type, id, etc.)
            sound: Custom sound file nomi (masalan: "challenge.wav")
        """
        if not settings.ONESIGNAL_REST_API_KEY:
            logger.warning("ONESIGNAL_REST_API_KEY sozlanmagan!")
            return False

        payload = {
            "app_id": settings.ONESIGNAL_APP_ID,
            "include_player_ids": [player_id],
            "headings": {"en": title},
            "contents": {"en": message},

            # ═══════════════════════════════════════
            # ANDROID - Telegram style notification
            # ═══════════════════════════════════════
            "android_channel_id": "high_priority_channel",
            "priority": 10,  # Maksimal prioritet
            "android_visibility": 1,  # Public - lock screen da ko'rinadi
            "android_accent_color": "FF4CAF50",  # Yashil rang

            # ═══════════════════════════════════════
            # iOS - Time Sensitive notification
            # ═══════════════════════════════════════
            "ios_interruption_level": "time_sensitive",
            "ios_relevance_score": 1.0,  # Maksimal relevance

            # ═══════════════════════════════════════
            # UMUMIY
            # ═══════════════════════════════════════
            "ttl": 86400,  # 24 soat
            "isAnyWeb": False,
        }

        # Custom sound va Android channel
        if sound:
            payload["ios_sound"] = sound
            sound_name = sound.replace(".wav", "").replace(".mp3", "")
            payload["android_sound"] = sound_name
            payload["android_channel_id"] = f"{sound_name}_channel"

        if data:
            payload["data"] = data

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    cls.BASE_URL,
                    json=payload,
                    headers=cls._get_headers(),
                )
                result = response.json()
                logger.info(f"🔔 OneSignal Response: {result}")

                if response.status_code == 200:
                    if result.get("recipients", 0) > 0:
                        logger.info(f"✅ Notification yuborildi: {player_id[:20]}... -> {result.get('recipients')} ta qabul qiluvchi")
                    else:
                        logger.warning(f"⚠️ Notification yuborildi, lekin 0 ta qabul qiluvchi! Player ID: {player_id[:30]}")
                    return True
                else:
                    logger.error(f"❌ OneSignal xato: {result}")
                    return False
        except Exception as e:
            logger.error(f"❌ Notification yuborishda xato: {e}")
            return False

    @classmethod
    async def send_to_players(
        cls,
        player_ids: List[str],
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Bir nechta o'yinchiga notification yuborish"""
        if not settings.ONESIGNAL_REST_API_KEY:
            logger.warning("ONESIGNAL_REST_API_KEY sozlanmagan!")
            return False

        if not player_ids:
            return False

        payload = {
            "app_id": settings.ONESIGNAL_APP_ID,
            "include_player_ids": player_ids,
            "headings": {"en": title},
            "contents": {"en": message},
        }

        if data:
            payload["data"] = data

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    cls.BASE_URL,
                    json=payload,
                    headers=cls._get_headers(),
                )
                response.raise_for_status()
                logger.info(f"Notification yuborildi: {len(player_ids)} ta o'yinchiga")
                return True
        except Exception as e:
            logger.error(f"Notification yuborishda xato: {e}")
            return False

    # ══════════════════════════════════════════════════════════
    # O'YINGA OID NOTIFICATIONLAR
    # ══════════════════════════════════════════════════════════

    @classmethod
    async def send_challenge_notification(
        cls,
        player_id: str,
        challenger_name: str,
        match_id: str,
        mode: str = "friendly",
        bet_amount: int = 0,
    ) -> bool:
        """Challenge kelganda notification"""
        title = "⚽ Yangi Challenge!"

        if bet_amount > 0:
            message = f"{challenger_name} sizni {bet_amount} tanga bilan o'yinga chaqirmoqda!"
        else:
            message = f"{challenger_name} sizni {mode} o'yiniga chaqirmoqda!"

        data = {
            "type": "challenge",
            "match_id": match_id,
            "challenger_name": challenger_name,
        }

        return await cls.send_to_player(
            player_id, title, message, data, sound="challenge.wav"
        )

    @classmethod
    async def send_friend_request_notification(
        cls,
        player_id: str,
        requester_name: str,
        requester_id: str,
    ) -> bool:
        """Do'stlik so'rovi kelganda notification"""
        title = "👥 Do'stlik so'rovi"
        message = f"{requester_name} sizga do'stlik so'rovi yubordi"

        data = {
            "type": "friend_request",
            "user_id": requester_id,
            "requester_name": requester_name,
        }

        return await cls.send_to_player(
            player_id, title, message, data, sound="friend_request.wav"
        )

    @classmethod
    async def send_friend_accepted_notification(
        cls,
        player_id: str,
        friend_name: str,
        friend_id: str,
    ) -> bool:
        """Do'stlik qabul qilinganda notification"""
        title = "✅ Do'stlik qabul qilindi"
        message = f"{friend_name} do'stlik so'rovingizni qabul qildi"

        data = {
            "type": "friend_accepted",
            "user_id": friend_id,
            "friend_name": friend_name,
        }

        return await cls.send_to_player(player_id, title, message, data)

    @classmethod
    async def send_match_reminder_notification(
        cls,
        player_id: str,
        opponent_name: str,
        match_id: str,
        minutes_left: int = 5,
    ) -> bool:
        """Match boshlanishiga oz qolganida notification"""
        title = "⏰ O'yin boshlanmoqda!"
        message = f"{opponent_name} bilan o'yiningizga {minutes_left} daqiqa qoldi"

        data = {
            "type": "match_reminder",
            "match_id": match_id,
            "opponent_name": opponent_name,
        }

        return await cls.send_to_player(player_id, title, message, data)

    @classmethod
    async def send_match_result_notification(
        cls,
        player_id: str,
        opponent_name: str,
        result: str,  # win, lose, draw
        score: str,
        coins_change: int = 0,
    ) -> bool:
        """O'yin natijasi haqida notification"""
        if result == "win":
            title = "🏆 G'alaba!"
            message = f"{opponent_name} ustidan {score} hisobida g'alaba qozondinginz!"
        elif result == "lose":
            title = "😔 Mag'lubiyat"
            message = f"{opponent_name} ga {score} hisobida yutqazdingiz"
        else:
            title = "🤝 Durrang"
            message = f"{opponent_name} bilan {score} hisobida durrang"

        if coins_change > 0:
            message += f" (+{coins_change} tanga)"
        elif coins_change < 0:
            message += f" ({coins_change} tanga)"

        data = {
            "type": "match_result",
            "result": result,
            "score": score,
        }

        return await cls.send_to_player(player_id, title, message, data)


# Sinxron versiya (background task uchun)
def send_challenge_notification_sync(
    player_id: str,
    challenger_name: str,
    match_id: str,
    mode: str = "friendly",
    bet_amount: int = 0,
) -> bool:
    """Challenge notification (sinxron)"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        NotificationService.send_challenge_notification(
            player_id, challenger_name, match_id, mode, bet_amount
        )
    )


def send_friend_request_notification_sync(
    player_id: str,
    requester_name: str,
    requester_id: str,
) -> bool:
    """Do'stlik so'rovi notification (sinxron)"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        NotificationService.send_friend_request_notification(
            player_id, requester_name, requester_id
        )
    )
