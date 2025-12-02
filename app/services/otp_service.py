# app/services/otp_service.py
import redis
import random
import logging
from typing import Optional, Tuple
from app.core.config import settings
from app.services.email_service import send_otp_email

logger = logging.getLogger(__name__)

# Redis connection
try:
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
except redis.ConnectionError:
    logger.warning("Redis ulanmadi! OTP faqat xotirada saqlanadi.")
    redis_client = None


# In-memory fallback (dev uchun)
_otp_store = {}
_attempt_store = {}


def _get_otp_key(email: str) -> str:
    return f"otp:{email}"


def _get_attempts_key(email: str) -> str:
    return f"otp_attempts:{email}"


def _get_block_key(email: str) -> str:
    return f"otp_blocked:{email}"


def is_blocked(email: str) -> Tuple[bool, int]:
    """
    Email bloklangan yoki yo'qligini tekshirish
    Returns: (blocked, remaining_seconds)
    """
    block_key = _get_block_key(email)
    
    if redis_client:
        ttl = redis_client.ttl(block_key)
        if ttl > 0:
            return True, ttl
        return False, 0
    else:
        import time
        block_data = _attempt_store.get(block_key)
        if block_data and time.time() < block_data:
            return True, int(block_data - time.time())
        return False, 0


def increment_attempts(email: str) -> int:
    """
    Urinishlar sonini oshirish
    Returns: joriy urinishlar soni
    """
    attempts_key = _get_attempts_key(email)
    
    if redis_client:
        attempts = redis_client.incr(attempts_key)
        if attempts == 1:
            redis_client.expire(attempts_key, settings.OTP_EXPIRATION_SECONDS * 2)
        
        if attempts >= settings.OTP_MAX_ATTEMPTS:
            block_key = _get_block_key(email)
            redis_client.setex(block_key, settings.OTP_BLOCK_MINUTES * 60, "1")
            redis_client.delete(attempts_key)
        
        return attempts
    else:
        _attempt_store[attempts_key] = _attempt_store.get(attempts_key, 0) + 1
        return _attempt_store[attempts_key]


def reset_attempts(email: str):
    """Urinishlarni nolga qaytarish"""
    attempts_key = _get_attempts_key(email)
    
    if redis_client:
        redis_client.delete(attempts_key)
    else:
        _attempt_store.pop(attempts_key, None)


def generate_and_save_otp(email: str) -> str:
    """
    OTP kod yaratish va saqlash
    """
    # Bloklangan bo'lsa xato qaytarish
    blocked, remaining = is_blocked(email)
    if blocked:
        raise ValueError(f"Juda ko'p urinish. {remaining} soniyadan keyin qayta urinib ko'ring.")
    
    # 6 xonali kod
    code = str(random.randint(100000, 999999))
    otp_key = _get_otp_key(email)
    
    if redis_client:
        redis_client.setex(otp_key, settings.OTP_EXPIRATION_SECONDS, code)
    else:
        import time
        _otp_store[otp_key] = {
            "code": code,
            "expires": time.time() + settings.OTP_EXPIRATION_SECONDS
        }
    
    # Email orqali yuborish (Resend)
    email_sent = send_otp_email(email, code)

    # Agar email yuborilmasa va DEBUG mode bo'lsa, terminalga chiqarish
    if not email_sent and settings.DEBUG:
        print(f"\n{'='*50}")
        print(f"📨 OTP KOD (DEV MODE - EMAIL YUBORILMADI)")
        print(f"📧 EMAIL: {email}")
        print(f"🔑 KOD:   {code}")
        print(f"⏰ MUDDAT: {settings.OTP_EXPIRATION_SECONDS} soniya")
        print(f"{'='*50}\n")
    
    logger.info(f"OTP yuborildi: {email}")
    return code


def verify_otp_in_redis(email: str, code: str) -> bool:
    """
    OTP kodni tekshirish
    """
    # Bloklangan bo'lsa
    blocked, remaining = is_blocked(email)
    if blocked:
        raise ValueError(f"Juda ko'p urinish. {remaining} soniyadan keyin qayta urinib ko'ring.")
    
    otp_key = _get_otp_key(email)
    
    if redis_client:
        stored_code = redis_client.get(otp_key)
    else:
        import time
        data = _otp_store.get(otp_key)
        if data and time.time() < data["expires"]:
            stored_code = data["code"]
        else:
            stored_code = None
    
    if stored_code and stored_code == code:
        # Muvaffaqiyatli - kodni va urinishlarni o'chirish
        if redis_client:
            redis_client.delete(otp_key)
        else:
            _otp_store.pop(otp_key, None)
        
        reset_attempts(email)
        logger.info(f"OTP tasdiqlandi: {email}")
        return True
    
    # Noto'g'ri kod - urinishni hisoblash
    attempts = increment_attempts(email)
    remaining_attempts = settings.OTP_MAX_ATTEMPTS - attempts
    
    if remaining_attempts > 0:
        logger.warning(f"Noto'g'ri OTP: {email}, qolgan urinishlar: {remaining_attempts}")
    else:
        logger.warning(f"Email bloklandi: {email}")
    
    return False


def get_remaining_attempts(email: str) -> int:
    """Qolgan urinishlar sonini olish"""
    attempts_key = _get_attempts_key(email)
    
    if redis_client:
        attempts = redis_client.get(attempts_key)
        attempts = int(attempts) if attempts else 0
    else:
        attempts = _attempt_store.get(attempts_key, 0)
    
    return max(0, settings.OTP_MAX_ATTEMPTS - attempts)
