"""SMS yuborish va telefon raqamini OTP kod bilan tasdiqlash.

Ikki rejim:

* **Test rejimi** (standart) — SMS yuborilmaydi, kod javobda `dev_otp`
  sifatida qaytadi va logga yoziladi. Provayder kredensiallari berilmaguncha
  ishlab turadi.
* **Haqiqiy rejim** — `ESKIZ_EMAIL` va `ESKIZ_PASSWORD` muhit
  o'zgaruvchilari qo'yilsa avtomatik yoqiladi va SMS haqiqatda yuboriladi.

Kredensiallarni `backend/.env` fayliga yozish kifoya (namuna: `.env.example`)
— `config/settings.py` uni ishga tushishda muhitga yuklaydi.

Rejimni majburan belgilash uchun: `SMS_DEV_MODE=True/False`.
Tekshirish uchun: `python manage.py sms_test +998901234567`.

Yangi provayder qo'shish uchun `SmsProvider` dan meros olib, `send()` ni
yozish va `get_provider()` ga qo'shish kifoya.
"""

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request

from django.utils import timezone

logger = logging.getLogger(__name__)

OTP_LENGTH = 6

# Eskiz bilan har bir HTTP so'rov uchun kutish chegarasi (soniya). Provayder
# javob bermay qolsa ro'yxatdan o'tish so'rovi cheksiz osilib qolmasin.
REQUEST_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Sozlamalar
# ---------------------------------------------------------------------------


def _from_file(name):
    """`sms_credentials.py` faylidagi qiymat (bo'lmasa bo'sh satr).

    Fayl vaqtinchalik — Eskiz tiketi hal bo'lgunicha loyiha hech qanday
    muhit sozlamasisiz ishlashi uchun. Fayl o'chirilsa ham hech narsa
    buzilmaydi.

    Testlarda bu fayl ATAYLAB o'qilmaydi: aks holda `manage.py test` haqiqiy
    kredensiallar bilan ishlab, Eskiz'ga chinakam so'rov yuborardi (sekin,
    pulli va natija tarmoqqa bog'liq bo'lib qolardi).
    """
    from django.conf import settings

    if getattr(settings, "TESTING", False):
        return ""
    try:
        from . import sms_credentials
    except ImportError:  # fayl o'chirilgan — normal holat
        return ""
    return str(getattr(sms_credentials, name, "") or "")


def _env(name, default=""):
    """Sozlamani o'qiydi: avval muhit, so'ng `sms_credentials.py` fayli.

    Muhit o'zgaruvchisi HAR DOIM ustun — shuning uchun qiymatlar keyinchalik
    `.env` ga yoki hosting Variables bo'limiga ko'chirilganda fayldagilari
    o'z-o'zidan e'tibordan qoladi va kodni o'zgartirish kerak bo'lmaydi.

    Muhitni o'qishda nomdagi tasodifiy probellarga ham chidamli bo'lamiz:
    Railway/Heroku kabi panellarda nomni nusxalab qo'yishda oxiriga probel
    tushib qolishi mumkin ("ESKIZ_EMAIL "). Bunda oddiy `os.environ.get`
    hech narsa topmaydi va sabab uzoq vaqt aniqlanmay qoladi.
    """
    value = os.environ.get(name)
    if value is None or not value.strip():
        target = name.strip().upper()
        for key, val in os.environ.items():
            if key.strip().upper() == target and val and val.strip():
                value = val
                break
    if value is None or not value.strip():
        value = _from_file(name)
    return (value or default).strip()


def credentials_source():
    """Kredensiallar qayerdan olinayotgani — tashxis uchun."""
    if os.environ.get("ESKIZ_EMAIL", "").strip():
        return "muhit (env)"
    if _from_file("ESKIZ_EMAIL").strip():
        return "sms_credentials.py fayli (vaqtinchalik)"
    return "topilmadi"


def _flag(name, default=False):
    """Muhitdagi bayroqni o'qiydi ("1/true/yes" — yoqilgan)."""
    raw = _env(name).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def has_credentials():
    """Eskiz kredensiallari qo'yilganmi."""
    return bool(_env("ESKIZ_EMAIL") and _env("ESKIZ_PASSWORD"))


def is_test_mode():
    """Test rejimi: SMS yuborilmaydi, kod javobda `dev_otp` bo'lib qaytadi.

    Qoida: kredensiallar bo'lmasa — har doim test rejimi. Kredensiallar bor
    bo'lsa haqiqiy rejim; uni faqat `SMS_DEV_MODE=True` bilan ATAYLAB
    o'chirish mumkin (masalan xarajatni to'xtatish kerak bo'lsa).

    Ilgari `SMS_DEV_MODE` ning istalgan qiymati (jumladan "False") ustun
    turardi va kredensiallar qo'yilgani bilan SMS ketmay qolardi.
    """
    if not has_credentials():
        return True
    return _flag("SMS_DEV_MODE")


def otp_template():
    """OTP matni shabloni. `{code}` haqiqiy kod bilan almashtiriladi.

    Eskiz faqat OLDINDAN TASDIQLANGAN shablonlarni yuboradi va matn
    tasdiqlangan variantga aynan mos kelishi kerak. Moderatsiyada matn biroz
    o'zgarsa, kodni qayta joylashtirmasdan `SMS_OTP_TEMPLATE` orqali moslash
    mumkin.
    """
    return _env("SMS_OTP_TEMPLATE") or (
        "Savin: tasdiqlash kodingiz {code}. Hech kimga aytmang."
    )


def diagnostics():
    """SMS sozlamalari holati — tashxis uchun (maxfiy QIYMATLAR qaytmaydi)."""
    # Muhitda "ESKIZ" so'zi bor o'zgaruvchilarning faqat NOMLARI —
    # nomda ko'rinmas belgi yoki xato bo'lsa shu yerdan bilinadi.
    found = {}
    for name, value in os.environ.items():
        if "ESKIZ" in name.upper():
            found[repr(name)] = len((value or "").strip())

    email = _env("ESKIZ_EMAIL")
    return {
        "has_credentials": has_credentials(),
        "test_mode": is_test_mode(),
        "provider": "console" if is_test_mode() else "eskiz",
        "credentials_source": credentials_source(),
        "sender": _env("ESKIZ_SENDER", "4546"),
        "email_set": bool(email),
        "password_set": bool(_env("ESKIZ_PASSWORD")),
        "sms_dev_mode_raw": _env("SMS_DEV_MODE") or None,
        "otp_template": otp_template(),
        "test_text_fallback": _flag("ESKIZ_TEST_TEXT_FALLBACK"),
        "otp_in_response": _flag("SMS_ALLOW_OTP_IN_RESPONSE"),
        "token_cached": bool(_TOKEN_CACHE.get("token")),
        # Nom -> qiymat uzunligi (qiymatning o'zi emas)
        "eskiz_env_names": found or "topilmadi",
    }


# ---------------------------------------------------------------------------
# Telefon raqami
# ---------------------------------------------------------------------------


def normalize_phone(phone):
    """Raqamni Eskiz kutgan shaklga keltiradi: `998XXXXXXXXX` (12 raqam).

    Raqam ilovadan "+998901234567" ko'rinishida keladi, lekin admin/biznes
    panelida qo'lda kiritilganda "+998 90 123 45 67", "90 123 45 67" yoki
    "8 90 123 45 67" bo'lishi mumkin. Bularning hammasi bitta shaklga
    keltiriladi — aks holda Eskiz raqamni rad etadi va SMS ketmaydi.

    Tanib bo'lmasa bo'sh satr qaytadi (chaqiruvchi buni xato deb qaraydi).
    """
    digits = re.sub(r"\D", "", phone or "")

    if digits.startswith("00"):        # xalqaro prefiks: 00998...
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("8"):  # ichki terish: 8 90 ...
        digits = digits[1:]
    if len(digits) == 9:               # operator kodidan boshlangan: 901234567
        digits = "998" + digits

    if len(digits) == 12 and digits.startswith("998"):
        return digits
    return ""


def _otp_key(phone):
    """OTP bazada saqlanadigan kalit — raqam shakli farq qilsa ham bir xil.

    Ro'yxatdan o'tishda "+998901234567", tasdiqlashda "998901234567" kelsa
    ham bitta yozuv topilishi kerak.
    """
    return normalize_phone(phone) or re.sub(r"\D", "", phone or "") or (phone or "").strip()


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


# Eskiz tokeni 30 kun amal qiladi. Uni jarayon xotirasida saqlaymiz — aks
# holda HAR BIR SMS uchun alohida login so'rovi ketardi (sekin va provayder
# tomonidan cheklanishi mumkin). Kalit sifatida email ishlatiladi: kredensial
# almashsa kesh o'zidan bekor bo'ladi.
_TOKEN_CACHE = {"key": None, "token": None, "expires_at": 0.0}
_TOKEN_LOCK = threading.Lock()
_TOKEN_TTL = 12 * 60 * 60  # 12 soat (Eskiz 30 kun beradi — ehtiyot uchun kam)


def _forget_token():
    with _TOKEN_LOCK:
        _TOKEN_CACHE.update({"key": None, "token": None, "expires_at": 0.0})


def _short(payload, limit=300):
    """Javobni logga sig'adigan qilib qisqartiradi."""
    if payload is None:
        return "(bo'sh javob)"
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"


class EskizSmsProvider(SmsProvider):
    """Eskiz.uz (O'zbekistondagi keng tarqalgan SMS provayder)."""

    BASE = "https://notify.eskiz.uz/api"

    # Eskiz hisobi "test" rolida bo'lsa yoki matn hali moderatsiyadan
    # o'tmagan bo'lsa, faqat shu standart matnni qabul qiladi.
    ESKIZ_TEST_TEXT = "Bu Eskiz dan test"

    def __init__(self):
        self.email = _env("ESKIZ_EMAIL")
        self.password = _env("ESKIZ_PASSWORD")
        self.sender = _env("ESKIZ_SENDER", "4546")

    # -- HTTP --------------------------------------------------------------

    def _request(self, path, data=None, token=None, method="POST"):
        """`(http_status, javob)` qaytaradi.

        HTTP xatosida (4xx/5xx) ham istisno ko'tarilmaydi — Eskiz sababni
        aynan javob tanasida yozadi ("message": "..."), va uni ko'rmasdan
        muammoni topib bo'lmaydi. Faqat tarmoq uzilishi istisno ko'taradi.
        """
        url = f"{self.BASE}{path}"
        body = json.dumps(data).encode() if data is not None else None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return resp.status, _parse_json(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, _parse_json(exc.read())

    # -- Token -------------------------------------------------------------

    def _login(self):
        status, data = self._request(
            "/auth/login", {"email": self.email, "password": self.password}
        )
        token = ((data or {}).get("data") or {}).get("token")
        if not token:
            logger.error(
                "Eskiz: token olinmadi (HTTP %s). Javob: %s. "
                "ESKIZ_EMAIL/ESKIZ_PASSWORD to'g'riligini tekshiring.",
                status,
                _short(data),
            )
        return token

    def _token(self, refresh=False):
        key = self.email
        now = time.time()
        with _TOKEN_LOCK:
            if (
                not refresh
                and _TOKEN_CACHE["token"]
                and _TOKEN_CACHE["key"] == key
                and _TOKEN_CACHE["expires_at"] > now
            ):
                return _TOKEN_CACHE["token"]

        token = self._login()
        if token:
            with _TOKEN_LOCK:
                _TOKEN_CACHE.update(
                    {"key": key, "token": token, "expires_at": time.time() + _TOKEN_TTL}
                )
        return token

    # -- Yuborish ----------------------------------------------------------

    def _post_message(self, number, text, token):
        return self._request(
            "/message/sms/send",
            {"mobile_phone": number, "message": text, "from": self.sender},
            token=token,
        )

    def send(self, phone, text):
        if not (self.email and self.password):
            logger.error("Eskiz kredensiallari yo'q — SMS yuborilmadi (%s)", phone)
            return False

        number = normalize_phone(phone)
        if not number:
            logger.error("SMS yuborilmadi — raqam noto'g'ri: %r", phone)
            return False

        try:
            token = self._token()
            if not token:
                return False

            status, data = self._post_message(number, text, token)

            # Token muddati tugagan/bekor qilingan bo'lsa bir marta yangilab
            # qayta urinamiz — foydalanuvchi buni sezmasligi kerak.
            if status in (401, 403) and not _is_template_error(status, data):
                _forget_token()
                token = self._token(refresh=True)
                if not token:
                    return False
                status, data = self._post_message(number, text, token)

            if _is_accepted(status, data):
                logger.info("SMS yuborildi: %s (id=%s)", number, (data or {}).get("id"))
                return True

            logger.error(
                "Eskiz SMSni qabul qilmadi (HTTP %s) — %s. Javob: %s",
                status,
                number,
                _short(data),
            )
            self._maybe_send_test_text(number, token, status, data)
            return False
        except urllib.error.URLError as exc:
            logger.error("Eskiz bilan aloqa yo'q (%s): %s", number, exc.reason)
            return False

    def _maybe_send_test_text(self, number, token, status, data):
        """Shablon tasdiqlanmagan bo'lsa Eskiz'ning standart test matnini yuboradi.

        Maqsad: hisob hali "test" rolida bo'lgan davrda ham foydalanuvchiga
        SMS jismonan borib tegsin (kanal ishlayotgani ko'rinsin). Lekin u
        tasdiqlash kodini OLMAYDI — shuning uchun `send()` baribir `False`
        qaytaradi va chaqiruvchi zaxira yo'lini ishlatadi.

        Standart holatda o'chiq; `ESKIZ_TEST_TEXT_FALLBACK=True` bilan yoqiladi.
        """
        if not _is_template_error(status, data) or not _flag("ESKIZ_TEST_TEXT_FALLBACK"):
            return

        logger.warning(
            "Eskiz matnni rad etdi — standart test matni yuborilmoqda (%s). "
            "Shablonni my.eskiz.uz da moderatsiyaga yuboring, aks holda "
            "foydalanuvchi tasdiqlash kodini OLMAYDI.",
            number,
        )
        try:
            fb_status, fb_data = self._post_message(number, self.ESKIZ_TEST_TEXT, token)
        except urllib.error.URLError as exc:
            logger.error("Test matni ham yuborilmadi (%s): %s", number, exc.reason)
            return

        if _is_accepted(fb_status, fb_data):
            logger.info("Test matni yuborildi: %s (id=%s)", number, (fb_data or {}).get("id"))
        else:
            logger.error(
                "Test matni ham qabul qilinmadi (HTTP %s) — %s. Javob: %s",
                fb_status,
                number,
                _short(fb_data),
            )


def _parse_json(raw):
    try:
        return json.loads(raw or b"{}")
    except (ValueError, TypeError):
        # HTML xato sahifasi ham kelishi mumkin — o'sha holicha logga tushsin
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        return {"raw": (raw or "")[:500]}


def _is_accepted(status, data):
    """Eskiz SMSni navbatga oldimi.

    Muvaffaqiyatda HTTP 200 va `{"status": "waiting", "id": ...}` qaytadi.
    Ba'zi xatolarda ham HTTP 200 keladi, lekin `status` "error" bo'ladi —
    faqat HTTP kodga qarab bo'lmaydi.
    """
    if not 200 <= int(status or 0) < 300:
        return False
    payload_status = str((data or {}).get("status") or "").lower()
    return payload_status not in ("error", "fail", "failed")


def _is_template_error(status, data):
    """Matn/shablon rad etilgan xatolimi (kredensial, raqam yoki tarmoq emas)."""
    if int(status or 0) not in (400, 403, 422):
        return False
    message = str((data or {}).get("message") or "").lower()
    # 403 token muammosi ham bo'lishi mumkin — uni shablon xatosi deb
    # hisoblamaymiz, aks holda tokenni yangilash yo'li ishlamay qoladi.
    if int(status) == 403 and ("token" in message or "unauthenticated" in message):
        return False
    # "Number is forbidden" — matn emas, RAQAM muammosi (test rejimidagi hisob
    # faqat o'ziga ruxsat berilgan raqamlarga yubora oladi). Bunda standart
    # test matnini yuborish ham xuddi shu xato bilan qaytadi — urinmaymiz.
    if "number" in message or "номер" in message or "raqam" in message:
        return False
    return True


def get_provider():
    if is_test_mode():
        return ConsoleSmsProvider()
    return EskizSmsProvider()


def send_sms(phone, text):
    """SMS yuborishning yagona kirish nuqtasi.

    Hech qachon istisno ko'tarmaydi — SMS yordamchi xabar bo'lgani uchun
    uning xatosi asosiy oqimni (biznesni tasdiqlash, kassir qo'shish va h.k.)
    to'xtatmasligi kerak. Muvaffaqiyat/muvaffaqiyatsizlik `bool` bilan
    qaytadi, sabab esa logda bo'ladi.
    """
    try:
        return bool(get_provider().send(phone, text))
    except Exception:  # noqa: BLE001 — asosiy oqim buzilmasin
        logger.exception("SMS yuborishda kutilmagan xatolik (%s)", phone)
        return False


def check_connection():
    """Kredensiallarni jonli tekshiradi (SMS yubormasdan).

    Qaytaradi: `(ok, xabar)`. `manage.py sms_test` shu orqali ishlaydi.
    """
    if not has_credentials():
        return False, "ESKIZ_EMAIL / ESKIZ_PASSWORD qo'yilmagan (test rejimi)."
    provider = EskizSmsProvider()
    try:
        token = provider._token(refresh=True)
    except urllib.error.URLError as exc:
        return False, f"Eskiz bilan aloqa yo'q: {exc.reason}"
    if not token:
        return False, "Login qabul qilinmadi — email yoki parol noto'g'ri."
    return True, "Eskiz bilan aloqa bor, token olindi."


def template_label(item):
    """Eskiz shablon yozuvini bitta satrga aylantiradi."""
    if not isinstance(item, dict):
        return str(item)
    text = item.get("template") or item.get("text") or str(item)
    state = item.get("status")
    return f"{text}   [{state}]" if state else str(text)


def account_info():
    """Eskiz hisobi holati: rol, balans, tasdiqlangan shablonlar.

    Nima uchun kerak: kredensiallar to'g'ri bo'lsa ham SMS ketmasligi mumkin —
    hisob hali "test" rolida bo'lsa yoki matn moderatsiyadan o'tmagan bo'lsa
    Eskiz o'z matningizni rad etadi. Bu funksiya sababni SMS yuborishdan
    OLDIN ko'rsatadi.

    Qaytaradi: `(ok, ma'lumot_lug'ati | xato_matni)`.
    """
    if not has_credentials():
        return False, "ESKIZ_EMAIL / ESKIZ_PASSWORD qo'yilmagan."

    provider = EskizSmsProvider()
    try:
        token = provider._token(refresh=True)
        if not token:
            return False, "Login qabul qilinmadi — email yoki parol noto'g'ri."
        _status, user = provider._request("/auth/user", token=token, method="GET")
        _status, templates = provider._request("/user/templates", token=token, method="GET")
    except urllib.error.URLError as exc:
        return False, f"Eskiz bilan aloqa yo'q: {exc.reason}"

    data = (user or {}).get("data") or {}
    items = (templates or {}).get("result") or (templates or {}).get("data") or []
    return True, {
        "name": data.get("name") or "—",
        "role": data.get("role") or "—",
        "status": data.get("status") or "—",
        "balance": data.get("balance"),
        "templates": [template_label(i) for i in items],
    }


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------


def hash_code(phone, code):
    """Kod ochiq saqlanmaydi — telefon bilan birga xeshlanadi."""
    from django.conf import settings

    salt = getattr(settings, "SECRET_KEY", "")
    return hashlib.sha256(f"{salt}:{_otp_key(phone)}:{code}".encode()).hexdigest()


def generate_code():
    """Tasodifiy 6 xonali kod.

    `secrets` ishlatiladi — `random` bashorat qilinadigan bo'lgani uchun
    tasdiqlash kodiga yaramaydi (bir nechta kodni ko'rgan hujumchi keyingisini
    hisoblab chiqishi mumkin).
    """
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def create_and_send(phone):
    """Yangi OTP yaratadi va yuboradi.

    Qaytaradi: `(otp, dev_code, sent)`
      * `dev_code` — kod javobda qaytadimi. Ikki holatda to'ladi: test
        rejimida, va `SMS_ALLOW_OTP_IN_RESPONSE` yoqilgan holda SMS ketmasa
        (vaqtinchalik zaxira yo'l — pastga qarang);
      * `sent` — SMS provayder xabarni qabul qildimi. `False` va `dev_code`
        ham bo'sh bo'lsa chaqiruvchi foydalanuvchiga halol xato ko'rsatishi
        kerak: aks holda u "kod yuborildi" ekranida kelmaydigan SMSni kutib
        qoladi.
    """
    from datetime import timedelta

    from .models import PhoneOtp

    key = _otp_key(phone)

    # Eski faol kodlarni bekor qilamiz — bir vaqtda bitta kod ishlasin
    PhoneOtp.objects.filter(phone=key, is_used=False).update(is_used=True)

    code = generate_code()
    otp = PhoneOtp.objects.create(
        phone=key,
        code_hash=hash_code(phone, code),
        expires_at=timezone.now() + timedelta(seconds=PhoneOtp.TTL_SECONDS),
    )

    sent = send_sms(phone, otp_template().replace("{code}", code))

    dev_code = None
    if is_test_mode():
        dev_code = code
    elif not sent:
        logger.error("Tasdiqlash kodi yetkazilmadi: %s", key)
        # VAQTINCHALIK ZAXIRA YO'L: Eskiz hisobi hali "test" rolida bo'lgani
        # (yoki shablon tasdiqlanmagani) uchun SMS ketmayapti. Bayroq
        # yoqilgan bo'lsa kodni javobda qaytaramiz — ro'yxatdan o'tish barcha
        # raqamlar uchun xatosiz tugaydi. Eskiz shablonni tasdiqlagach bu yo'l
        # o'z-o'zidan ishlatilmay qoladi (`sent` True bo'ladi).
        if _flag("SMS_ALLOW_OTP_IN_RESPONSE"):
            logger.warning(
                "SMS_ALLOW_OTP_IN_RESPONSE yoqilgan — tasdiqlash kodi API "
                "javobida ochiq qaytmoqda (%s). Bu vaqtinchalik yechim: "
                "istalgan odam istalgan raqam nomidan kira oladi. Eskiz "
                "shabloni tasdiqlangach o'chiring.",
                key,
            )
            dev_code = code

    return otp, dev_code, sent


def seconds_until_resend(phone):
    """Qayta yuborishgacha qolgan soniya (0 bo'lsa yuborsa bo'ladi)."""
    from .models import PhoneOtp

    last = PhoneOtp.objects.filter(phone=_otp_key(phone)).order_by("-created_at").first()
    if not last:
        return 0
    passed = (timezone.now() - last.created_at).total_seconds()
    left = PhoneOtp.RESEND_COOLDOWN_SECONDS - passed
    return int(left) + 1 if left > 0 else 0


def verify(phone, code):
    """Kodni tekshiradi.

    Qaytaradi: `(ok, xato_matni)`.
    """
    from .models import PhoneOtp

    key = _otp_key(phone)
    otp = PhoneOtp.objects.filter(phone=key, is_used=False).order_by("-created_at").first()
    if not otp:
        return False, "Kod topilmadi. Qaytadan kod so'rang."
    if otp.is_expired:
        return False, "Kod muddati tugadi. Qaytadan kod so'rang."
    if otp.attempts >= PhoneOtp.MAX_ATTEMPTS:
        return False, "Urinishlar soni tugadi. Qaytadan kod so'rang."

    # Doimiy vaqtda solishtirish — xesh baytlarini javob tezligi orqali
    # birma-bir topib olishning oldini oladi.
    if not hmac.compare_digest(otp.code_hash, hash_code(phone, str(code).strip())):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        left = PhoneOtp.MAX_ATTEMPTS - otp.attempts
        if left <= 0:
            return False, "Kod noto'g'ri. Urinishlar tugadi, qaytadan kod so'rang."
        return False, f"Kod noto'g'ri. Yana {left} ta urinish qoldi."

    otp.is_used = True
    otp.save(update_fields=["is_used"])
    return True, ""
