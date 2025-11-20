from sqlalchemy import text
from app.core.database import engine

def test_connection():
    print("⏳ Baza bilan ulanish tekshirilmoqda...")
    try:
        # Bazaga ulanishga urinib ko'ramiz
        with engine.connect() as connection:
            # Oddiy SQL so'rov yuboramiz
            result = connection.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            
            print("\n✅ MUVAFFAQIYATLI ULANDI!")
            print(f"Baza nomi: cyberpitch_db")
            print(f"PostgreSQL versiyasi: {version}")
            
    except Exception as e:
        print("\n❌ ULANISHDA XATOLIK BO'LDI!")
        print(f"Xatolik sababi: {e}")

if __name__ == "__main__":
    test_connection()