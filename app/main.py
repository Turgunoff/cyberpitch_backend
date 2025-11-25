# app/main.py
from fastapi import FastAPI
from app.core.database import engine, Base
from app.api import auth 
from app.api import auth, tournaments  # tournaments qo'shing


# Jadvallarni yaratish (Eski jadvalni yangilash uchun)
# ESLATMA: Haqiqiy loyihada Alembic ishlatiladi, lekin hozir tezkor test uchun:
Base.metadata.drop_all(bind=engine) # Eskisini o'chiramiz (chunki yangi ustun qo'shdik)
Base.metadata.create_all(bind=engine) # Yangisini yaratamiz

app = FastAPI(
    title="CyberPitch API",
    version="1.0",
    description="Mobile Football League Backend"
)

# Routerni ulaymiz
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])

app.include_router(tournaments.router, prefix="/api/v1/tournaments", tags=["Tournaments"])

@app.get("/")
def read_root():
    return {"status": "Active", "message": "CyberPitch Server ishlamoqda! 🚀"}