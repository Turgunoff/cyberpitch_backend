from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# Bazaga ulanish motorini yaratish
engine = create_engine(settings.DATABASE_URL)

# Sessiya yaratuvchi
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Modellarni yaratish uchun asos
Base = declarative_base()

# Dependency (Har bir so'rov uchun baza sessiyasini ochib-yopish)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
