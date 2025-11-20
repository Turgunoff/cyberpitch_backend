import redis
import random

# Redisga ulanish
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def generate_and_save_otp(email: str) -> str:
    # 1. 6 xonali kod yaratamiz
    code = str(random.randint(100000, 999999))
    
    # 2. Redisga yozamiz (2 daqiqa turadi)
    r.setex(f"otp:{email}", 120, code)
    
    # 3. TERMINALGA CHIQARISH (MOCK)
    print(f"\n{'='*40}")
    print(f"📨 MOCK EMAIL YUBORILDI")
    print(f"KIMGA: {email}")
    print(f"KOD:   {code}")
    print(f"{'='*40}\n")
    
    return code

def verify_otp_in_redis(email: str, code: str) -> bool:
    stored_code = r.get(f"otp:{email}")
    if stored_code and stored_code == code:
        r.delete(f"otp:{email}") # Kodni ishlatib bo'lgach o'chiramiz
        return True
    return False