from pydantic import BaseModel, EmailStr

# 1. Login qilish uchun (faqat email so'raymiz)
class EmailLoginRequest(BaseModel):
    email: EmailStr

# 2. Kodni tasdiqlash uchun
class VerifyOTPRequest(BaseModel):
    email: EmailStr
    code: str

# 3. Server javobi (Token)
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    is_new_user: bool