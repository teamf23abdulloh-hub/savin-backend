"""SMS yuborish va telefon raqamini OTP kod bilan tasdiqlash.

Ikki rejim:

* **Test rejimi** (standart) — SMS yuborilmaydi, kod javobda `dev_otp`
  sifatida qaytadi va logga yoziladi. Provayder kredensiallari berilmaguncha
  ishlab turadi.
* **Haqiqiy rejim** — `ESKIZ_EMAIL` va `ESKIZ_PASSWORD` muhit
  o'zgaruvchilari qo'yilsa avtomatik yoqiladi va SMS haqiqatda yuboriladi.

Rejimni majburan belgilash uchun: `SMS_DEV_MODE=True/False`.

Yangi provayder qo'shish uchun `SmsProvider` dan meros olib, `send()` ni
yozish va `get_provider()` ga qo'shish kifoya.
"""

import hashlib
import json
import logging
import os
import random
import urllib.error
import urllib.request

from django.utils import timezone

logger = logging.getLogger(__name__)

OTP_LENGTH = 6


# ---------------------------------------------------------------------------
# Sozlamalar
# ---------------------------------------------------------------------------


def _env(name, default=""):
    return (os.environ.get(name) or default).strip()


def is_test_mode():
    """Kredensiallar bo'lmasa avtomatik test rejimi."""
    forced = _env("SMS_DEV_MODE")
    if forced:
        return forced.lower() in ("1", "true", "yes")
    return not (_env("ESKIZ_EMAIL") and _env("ESKIZ_PASSWORD"))


# ---------------------------------------------------------------------------
# Provayderlar
# ---------------------------------------------------------------------------


class SmsProvider:
    def send(self, phone, text):  # pragma: no cover - interfeys
        raise NotImplementedError


class ConsoleSmsProvider(SmsProvider):
    """Test rejimi — SMS yuborilmaydi, faqat logga yoziladi."""

    def send(self, phone, text):
        logger.info("[SMS-TEST] %s -> %s", phone, text)
        return True


class EskizSmsProvider(SmsProvider):
    """Eskiz.uz (O'zbekistondagi keng tarqalgan SMS provayder)."""

    BASE = "https://notify.eskiz.uz/api"

    def __init__(self):
        self.email = _env("ESKIZ_EMAIL")
        self.password = _env("ESKIZ_PASSWORD")
        self.sender = _env("ESKIZ_SENDER", "4546")
        self._token = None

    def _request(self, path, data=None, token=None, method="POST"):
        url = f"{self.BASE}{path}"
        body = json.dumps(data).encode() if data is not None else None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read() or b"{}")

    def _get_token(self):
        if self._token:
            return self._token
        data = self._request(
            "/auth/login", {"email": self.email, "password": self.password}
        )
        self._token = (data.get("data") or {}).get("token")
        return self._token

    def send(self, phone, text):
        try:
            token = self._get_token()
            if not token:
                logger.error("Eskiz: token olinmadi")
                return False
            self._request(
                "/message/sms/send",
                {
                    "mobile_phone": phone.lstrip("+"),
                    "message": text,
                    "from": self.sender,
                },
                token=token,
            )
            return True
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError):
            logger.exception("Eskiz orqali SMS yuborishda xatolik (%s)", phone)
            return False


def get_provider():
    if is_test_mode():
        return ConsoleSmsProvider()
    return EskizSmsProvider()


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------


def hash_code(phone, code):
    """Kod ochiq saqlanmaydi — telefon bilan birga xeshlanadi."""
    from django.conf import settings

    salt = getattr(settings, "SECRET_KEY", "")
    return hashlib.sha256(f"{salt}:{phone}:{code}".encode()).hexdigest()


def generate_code():
    """Tasodifiy 6 xonali kod. Test rejimida ham tasodifiy — javobda qaytadi."""
    return f"{random.randint(0, 10**OTP_LENGTH - 1):0{OTP_LENGTH}d}"


def create_and_send(phone):
    """Yangi OTP yaratadi va yuboradi.

    Qaytaradi: `(otp, dev_code)` — `dev_code` faqat test rejimida to'ldiriladi,
    haqiqiy rejimda hech qachon qaytmaydi.
    """
    from datetime import timedelta

    from .models import PhoneOtp

    # Eski faol kodlarni bekor qilamiz — bir vaqtda bitta kod ishlasin
    PhoneOtp.objects.filter(phone=phone, is_used=False).update(is_used=True)

    code = generate_code()
    otp = PhoneOtp.objects.create(
        phone=phone,
        code_hash=hash_code(phone, code),
        expires_at=timezone.now() + timedelta(seconds=PhoneOtp.TTL_SECONDS),
    )

    text = f"Savin: tasdiqlash kodingiz {code}. Hech kimga aytmang."
    get_provider().send(phone, text)

    return otp, (code if is_test_mode() else None)


def seconds_until_resend(phone):
    """Qayta yuborishgacha qolgan soniya (0 bo'lsa yuborsa bo'ladi)."""
    from .models import PhoneOtp

    last = PhoneOtp.objects.filter(phone=phone).order_by("-created_at").first()
    if not last:
        return 0
    passed = (timezone.now() - last.created_at).total_seconds()
    left = PhoneOtp.RESEND_COOLDOWN_SECONDS - passed
    return int(left) if left > 0 else 0


def verify(phone, code):
    """Kodni tekshiradi.

    Qaytaradi: `(ok, xato_matni)`.
    """
    from .models import PhoneOtp

    otp = PhoneOtp.objects.filter(phone=phone, is_used=False).order_by("-created_at").first()
    if not otp:
        return False, "Kod topilmadi. Qaytadan kod so'rang."
    if otp.is_expired:
        return False, "Kod muddati tugadi. Qaytadan kod so'rang."
    if otp.attempts >= PhoneOtp.MAX_ATTEMPTS:
        return False, "Urinishlar soni tugadi. Qaytadan kod so'rang."

    if otp.code_hash != hash_code(phone, str(code).strip()):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        left = PhoneOtp.MAX_ATTEMPTS - otp.attempts
        if left <= 0:
            return False, "Kod noto'g'ri. Urinishlar tugadi, qaytadan kod so'rang."
        return False, f"Kod noto'g'ri. Yana {left} ta urinish qoldi."

    otp.is_used = True
    otp.save(update_fields=["is_used"])
    return True, ""
