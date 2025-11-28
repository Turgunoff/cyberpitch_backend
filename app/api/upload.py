# app/api/upload.py
"""Rasm yuklash API"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from PIL import Image
import os
import uuid
import io

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.users import User

router = APIRouter()


def get_upload_path() -> str:
    """Upload papkasini yaratish va yo'lini qaytarish"""
    upload_path = os.path.join(settings.UPLOAD_DIR, settings.AVATAR_DIR)
    os.makedirs(upload_path, exist_ok=True)
    return upload_path


def optimize_image(image_data: bytes, size: int = 400, quality: int = 85) -> bytes:
    """
    Rasmni optimizatsiya qilish:
    - Kvadrat shaklga keltirish (markazdan kesish)
    - O'lchamini kamaytirish
    - JPEG formatga o'tkazish va sifatni sozlash
    """
    img = Image.open(io.BytesIO(image_data))

    # RGBA bo'lsa RGB ga o'tkazish
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    # Kvadrat qilib kesish (markazdan)
    width, height = img.size
    min_side = min(width, height)

    left = (width - min_side) // 2
    top = (height - min_side) // 2
    right = left + min_side
    bottom = top + min_side

    img = img.crop((left, top, right, bottom))

    # O'lchamini o'zgartirish
    img = img.resize((size, size), Image.Resampling.LANCZOS)

    # JPEG formatda saqlash
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)
    output.seek(0)

    return output.getvalue()


@router.post("/avatar", summary="Avatar yuklash")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Profil rasmini yuklash

    - Faqat JPG, PNG, WEBP formatlar qabul qilinadi
    - Maksimum hajm: 5MB
    - Rasm avtomatik 400x400 pikselga o'zgartiriladi
    - Sifat 85% da saqlanadi
    """
    profile = current_user.profile

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil topilmadi"
        )

    # Fayl turini tekshirish
    allowed_types = ['image/jpeg', 'image/png', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat JPG, PNG yoki WEBP formatdagi rasmlar qabul qilinadi"
        )

    # Fayl hajmini tekshirish
    contents = await file.read()
    if len(contents) > settings.MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rasm hajmi {settings.MAX_AVATAR_SIZE // (1024*1024)}MB dan oshmasligi kerak"
        )

    try:
        # Rasmni optimizatsiya qilish
        optimized = optimize_image(
            contents,
            size=settings.AVATAR_SIZE,
            quality=settings.AVATAR_QUALITY
        )

        # Eski rasmni o'chirish
        if profile.avatar_url:
            old_filename = profile.avatar_url.split('/')[-1]
            old_path = os.path.join(get_upload_path(), old_filename)
            if os.path.exists(old_path):
                os.remove(old_path)

        # Yangi fayl nomi
        filename = f"{uuid.uuid4()}.jpg"
        filepath = os.path.join(get_upload_path(), filename)

        # Faylni saqlash
        with open(filepath, 'wb') as f:
            f.write(optimized)

        # Avatar URL ni yangilash
        avatar_url = f"{settings.BASE_URL}/api/v1/upload/avatar/{filename}"
        profile.avatar_url = avatar_url

        db.commit()
        db.refresh(profile)

        return {
            "message": "Avatar muvaffaqiyatli yuklandi",
            "avatar_url": avatar_url,
            "file_size": len(optimized),
            "dimensions": f"{settings.AVATAR_SIZE}x{settings.AVATAR_SIZE}"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rasmni saqlashda xatolik: {str(e)}"
        )


@router.get("/avatar/{filename}", summary="Avatar olish")
async def get_avatar(filename: str):
    """Avatar rasmini olish (1 yil cache bilan)"""
    filepath = os.path.join(get_upload_path(), filename)

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rasm topilmadi"
        )

    return FileResponse(
        filepath,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=31536000",  # 1 yil cache
            "ETag": filename
        }
    )


@router.delete("/avatar", summary="Avatar o'chirish")
async def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Profil rasmini o'chirish"""
    profile = current_user.profile

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil topilmadi"
        )

    if not profile.avatar_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar mavjud emas"
        )

    # Faylni o'chirish
    filename = profile.avatar_url.split('/')[-1]
    filepath = os.path.join(get_upload_path(), filename)

    if os.path.exists(filepath):
        os.remove(filepath)

    profile.avatar_url = None
    db.commit()

    return {"message": "Avatar o'chirildi"}
