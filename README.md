# CyberPitch Backend - Tuzatilgan Versiya

## 🔧 Tuzatilgan Xatolar

### 1. **Kritik Xatolar**

#### ❌ `main.py` - Ma'lumotlar yo'qolishi xavfi
```python
# ESKI (XATO):
Base.metadata.drop_all(bind=engine)  # ⚠️ Barcha ma'lumotlar o'chadi!
Base.metadata.create_all(bind=engine)

# YANGI (TO'G'RI):
# Faqat mavjud bo'lmagan jadvallarni yaratadi
def init_db():
    Base.metadata.create_all(bind=engine)
```

#### ❌ `tournaments.py` API - `user_id` ishlatilmagan
```python
# ESKI (XATO):
participant = TournamentParticipant(
    tournament_id=tournament_id,
    # user_id=current_user.id  <-- Kommentda qolgan!
)

# YANGI (TO'G'RI):
participant = TournamentParticipant(
    tournament_id=tournament_id,
    user_id=current_user.id  # ✅ Haqiqiy user
)
```

#### ❌ `auth.py` - `get_current_user` dependency yo'q edi
```python
# security.py yaratildi - JWT authentication to'liq ishlaydi
```

---

### 2. **Xavfsizlik Xatolari**

#### ❌ OTP Brute-force himoyasi yo'q edi
```python
# YANGI: Rate limiting qo'shildi
OTP_MAX_ATTEMPTS = 5      # Maksimum urinishlar
OTP_BLOCK_MINUTES = 15    # Block vaqti
```

#### ❌ SECRET_KEY statik edi
```python
# ESKI:
SECRET_KEY = "juda_maxfiy_kalit_changeme"

# YANGI: .env dan o'qiladi yoki random generatsiya
SECRET_KEY = secrets.token_urlsafe(32)
```

#### ❌ Refresh token yo'q edi
```python
# YANGI: Access + Refresh token tizimi qo'shildi
```

---

### 3. **Model Xatolari**

#### ❌ Index va Constraint'lar yo'q edi
```python
# YANGI: UniqueConstraint qo'shildi
__table_args__ = (
    UniqueConstraint("tournament_id", "user_id", name="uq_tournament_user"),
)
```

#### ❌ Cascade delete yo'q edi
```python
# YANGI: Proper cascade
ForeignKey("users.id", ondelete="CASCADE")
```

---

### 4. **Schema Xatolari**

#### ❌ `auth.py` uchun schema yo'q edi
```python
# YANGI: app/schemas/auth.py yaratildi
```

#### ❌ Validation yo'q edi
```python
# YANGI: Pydantic validators qo'shildi
@field_validator("max_participants")
def validate_participants(cls, v):
    if v & (v - 1) != 0:
        raise ValueError("2 ning darajasi bo'lishi kerak")
```

---

## 📁 Yangi Loyiha Strukturasi

```
cyberpitch_backend/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py          # ✅ Tuzatildi
│   │   └── tournaments.py   # ✅ Tuzatildi
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # ✅ Kengaytirildi
│   │   ├── database.py      # ✅ Tuzatildi
│   │   └── security.py      # 🆕 Yangi
│   ├── models/
│   │   ├── __init__.py
│   │   ├── users.py         # ✅ Tuzatildi
│   │   └── tournaments.py   # ✅ Tuzatildi
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py          # 🆕 Yangi
│   │   ├── user.py          # ✅ Kengaytirildi
│   │   └── tournament.py    # ✅ Tuzatildi
│   ├── services/
│   │   ├── __init__.py
│   │   └── otp_service.py   # ✅ Tuzatildi
│   └── main.py              # ✅ Tuzatildi
├── migrations/
│   ├── env.py               # 🆕 Alembic
│   ├── script.py.mako
│   └── versions/
├── tests/
├── .env.example             # 🆕 Yangi
├── alembic.ini              # 🆕 Yangi
└── requirements.txt         # ✅ To'ldirildi
```

---

## 🚀 Ishga Tushirish

### 1. Virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# yoki
.\venv\Scripts\activate   # Windows
```

### 2. Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment variables
```bash
cp .env.example .env
# .env faylni tahrirlang
```

### 4. Database migration
```bash
# Birinchi marta
alembic revision --autogenerate -m "initial"
alembic upgrade head

# Keyingi o'zgarishlar
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### 5. Server
```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## 📝 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/send-code` | OTP yuborish |
| POST | `/api/v1/auth/verify-code` | OTP tekshirish |
| POST | `/api/v1/auth/refresh` | Token yangilash |
| POST | `/api/v1/auth/logout` | Chiqish |

### Tournaments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tournaments` | Ro'yxat |
| GET | `/api/v1/tournaments/featured` | Featured |
| GET | `/api/v1/tournaments/{id}` | Tafsilot |
| POST | `/api/v1/tournaments` | Yaratish (admin) |
| PATCH | `/api/v1/tournaments/{id}` | Yangilash (admin) |
| DELETE | `/api/v1/tournaments/{id}` | O'chirish (admin) |
| POST | `/api/v1/tournaments/{id}/join` | Qo'shilish |
| DELETE | `/api/v1/tournaments/{id}/leave` | Chiqish |
| GET | `/api/v1/tournaments/{id}/bracket` | Bracket |

---

## ⚠️ Muhim Eslatmalar

1. **Production'da `DEBUG=false` qiling** - Docs yopiladi
2. **SECRET_KEY ni o'zgartiring** - Yangi random kalit
3. **Redis o'rnating** - OTP uchun kerak
4. **Alembic migration ishlatiling** - `drop_all()` EMAS!

---

## 📞 Keyingi Qadamlar

1. [ ] WebSocket qo'shish (live updates)
2. [ ] Bracket generator yaratish
3. [ ] Admin panel
4. [ ] Unit testlar
5. [ ] Docker containerization
