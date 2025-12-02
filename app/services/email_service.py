# app/services/email_service.py
import resend
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# Resend API kalitini sozlash
resend.api_key = settings.RESEND_API_KEY


def send_otp_email(to_email: str, otp_code: str) -> bool:
    """
    OTP kodni email orqali yuborish

    Args:
        to_email: Qabul qiluvchi email
        otp_code: 6 xonali OTP kod

    Returns:
        bool: Muvaffaqiyatli yuborildi yoki yo'q
    """

    # API key tekshirish
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY sozlanmagan! Email yuborilmadi.")
        if settings.DEBUG:
            print(f"\n{'='*50}")
            print(f"📨 EMAIL YUBORILMADI (API KEY YO'Q)")
            print(f"📧 EMAIL: {to_email}")
            print(f"🔑 KOD:   {otp_code}")
            print(f"{'='*50}\n")
        return False

    # Chiroyli HTML shablon
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0a0a0a;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 40px;">
                <h1 style="color: #00ff88; font-size: 32px; margin: 0; font-weight: bold;">
                    ⚽ CyberPitch
                </h1>
                <p style="color: #666; margin-top: 8px; font-size: 14px;">
                    Futbol o'yini platformasi
                </p>
            </div>

            <!-- Main Content -->
            <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 16px; padding: 40px; border: 1px solid #00ff88;">
                <h2 style="color: #ffffff; text-align: center; margin: 0 0 10px 0; font-size: 20px;">
                    Tasdiqlash kodi
                </h2>
                <p style="color: #aaa; text-align: center; margin: 0 0 30px 0; font-size: 14px;">
                    Hisobingizga kirish uchun quyidagi kodni kiriting
                </p>

                <!-- OTP Code -->
                <div style="background: #0d0d0d; border-radius: 12px; padding: 24px; text-align: center; border: 2px dashed #00ff88;">
                    <span style="font-size: 42px; font-weight: bold; letter-spacing: 12px; color: #00ff88; font-family: 'Courier New', monospace;">
                        {otp_code}
                    </span>
                </div>

                <!-- Timer Warning -->
                <p style="color: #ff6b6b; text-align: center; margin-top: 24px; font-size: 14px;">
                    ⏰ Kod 2 daqiqa ichida amal qiladi
                </p>
            </div>

            <!-- Footer -->
            <div style="text-align: center; margin-top: 40px;">
                <p style="color: #666; font-size: 12px; margin: 0;">
                    Agar siz bu so'rovni yubormagan bo'lsangiz, ushbu xabarni e'tiborsiz qoldiring.
                </p>
                <p style="color: #444; font-size: 11px; margin-top: 16px;">
                    © 2025 CyberPitch. Barcha huquqlar himoyalangan.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        params = {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": f"🔐 CyberPitch - Tasdiqlash kodi: {otp_code}",
            "html": html_content
        }

        response = resend.Emails.send(params)

        logger.info(f"OTP email yuborildi: {to_email}, ID: {response.get('id', 'N/A')}")

        if settings.DEBUG:
            print(f"\n{'='*50}")
            print(f"✅ EMAIL YUBORILDI (RESEND)")
            print(f"📧 EMAIL: {to_email}")
            print(f"🔑 KOD:   {otp_code}")
            print(f"📨 ID:    {response.get('id', 'N/A')}")
            print(f"{'='*50}\n")

        return True

    except Exception as e:
        logger.error(f"Email yuborishda xato: {to_email}, Xato: {str(e)}")

        if settings.DEBUG:
            print(f"\n{'='*50}")
            print(f"❌ EMAIL YUBORISHDA XATO")
            print(f"📧 EMAIL: {to_email}")
            print(f"🔑 KOD:   {otp_code}")
            print(f"❗ XATO:  {str(e)}")
            print(f"{'='*50}\n")

        return False


def send_welcome_email(to_email: str, username: str) -> bool:
    """
    Yangi foydalanuvchiga xush kelibsiz emaili
    """
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY sozlanmagan!")
        return False

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0a0a0a;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <div style="text-align: center; margin-bottom: 40px;">
                <h1 style="color: #00ff88; font-size: 32px; margin: 0;">⚽ CyberPitch</h1>
            </div>

            <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 16px; padding: 40px; border: 1px solid #00ff88;">
                <h2 style="color: #00ff88; text-align: center; margin: 0 0 20px 0;">
                    🎉 Xush kelibsiz, {username}!
                </h2>
                <p style="color: #ddd; text-align: center; line-height: 1.6;">
                    CyberPitch oilasiga qo'shilganingiz bilan tabriklaymiz!
                    Endi siz dunyoning eng yaxshi futbol o'yinchilari bilan bellashishingiz mumkin.
                </p>
                <div style="text-align: center; margin-top: 30px;">
                    <span style="background: #00ff88; color: #000; padding: 12px 32px; border-radius: 8px; font-weight: bold; display: inline-block;">
                        O'yinni boshlang! ⚽
                    </span>
                </div>
            </div>

            <p style="color: #666; font-size: 12px; text-align: center; margin-top: 40px;">
                © 2025 CyberPitch. Barcha huquqlar himoyalangan.
            </p>
        </div>
    </body>
    </html>
    """

    try:
        params = {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": f"🎉 CyberPitch ga xush kelibsiz, {username}!",
            "html": html_content
        }

        resend.Emails.send(params)
        logger.info(f"Welcome email yuborildi: {to_email}")
        return True

    except Exception as e:
        logger.error(f"Welcome email xatosi: {to_email}, Xato: {str(e)}")
        return False
