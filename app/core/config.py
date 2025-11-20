from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Format: postgresql://user:password@host/database_name
    DATABASE_URL: str = "postgresql://cyber_admin:cyber_parol_2025@localhost/cyberpitch_db"
    
    # Xavfsizlik uchun kalitlar (keyinchalik o'zgartirasiz)
    SECRET_KEY: str = "juda_maxfiy_kalit_changeme"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()
