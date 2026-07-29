"""Payme va Click to'lov tizimlari bilan integratsiya.

Ikki rejim:

* **Test rejimi** (standart) — provayder kredensiallari qo'yilmagan bo'lsa
  avtomatik yoqiladi. To'lov havolasi bizning "test to'lov" sahifamizga
  olib boradi va oqimni uchdan-uchgacha sinab ko'rish mumkin.
* **Haqiqiy rejim** — quyidagi muhit o'zgaruvchilari qo'yilganda:

  Payme: `PAYME_MERCHANT_ID`, `PAYME_KEY`
  Click: `CLICK_SERVICE_ID`, `CLICK_MERCHANT_ID`, `CLICK_SECRET_KEY`

  `PAYMENTS_SANDBOX=True` bo'lsa provayderlarning sinov muhiti ishlatiladi
  (test.paycom.uz) — kredensiallar bor, lekin haqiqiy pul yechilmaydi.

Eslatma: Payme summani **tiyin**da (1 so'm = 100 tiyin), Click esa
so'mda kutadi.
"""

import base64
import hashlib
import os

# ---------------------------------------------------------------------------
# Sozlamalar
# ---------------------------------------------------------------------------


def _env(name, default=""):
    return (os.environ.get(name) or default).strip()


def payme_configured():
    return bool(_env("PAYME_MERCHANT_ID") and _env("PAYME_KEY"))


def click_configured():
    return bool(
        _env("CLICK_SERVICE_ID") and _env("CLICK_MERCHANT_ID") and _env("CLICK_SECRET_KEY")
    )


def is_test_mode(provider=None):
    """Kredensiallar bo'lmasa test rejimi."""
    forced = _env("PAYMENTS_TEST_MODE")
    if forced:
        return forced.lower() in ("1", "true", "yes")
    if provider == "payme":
        return not payme_configured()
    if provider == "click":
        return not click_configured()
    return not (payme_configured() or click_configured())


def is_sandbox():
    """Kredensiallar bor, lekin provayderning sinov muhiti ishlatilsin."""
    return _env("PAYMENTS_SANDBOX").lower() in ("1", "true", "yes")


def base_url():
    """Foydalanuvchi qaytadigan manzil (frontend yoki backend)."""
    return _env("PUBLIC_BASE_URL", "https://savin-backend-production.up.railway.app").rstrip("/")


# ---------------------------------------------------------------------------
# To'lov havolasini yasash
# ---------------------------------------------------------------------------


def payme_checkout_url(payment_id, amount_sum, return_url=None):
    """Payme checkout havolasi.

    Format: base64("m=<merchant>;ac.order_id=<id>;a=<tiyin>;c=<return>")
    """
    merchant = _env("PAYME_MERCHANT_ID")
    amount_tiyin = int(round(float(amount_sum) * 100))
    parts = [f"m={merchant}", f"ac.order_id={payment_id}", f"a={amount_tiyin}"]
    if return_url:
        parts.append(f"c={return_url}")
    payload = ";".join(parts)
    encoded = base64.b64encode(payload.encode()).decode()
    host = "https://test.paycom.uz" if is_sandbox() else "https://checkout.paycom.uz"
    return f"{host}/{encoded}"


def click_checkout_url(payment_id, amount_sum, return_url=None):
    """Click to'lov havolasi."""
    service_id = _env("CLICK_SERVICE_ID")
    merchant_id = _env("CLICK_MERCHANT_ID")
    url = (
        "https://my.click.uz/services/pay"
        f"?service_id={service_id}&merchant_id={merchant_id}"
        f"&amount={float(amount_sum):.2f}&transaction_param={payment_id}"
    )
    if return_url:
        url += f"&return_url={return_url}"
    return url


def test_checkout_url(payment_id):
    """Test rejimidagi to'lov sahifasi (o'zimizniki)."""
    return f"{base_url()}/api/v1/payments/test/{payment_id}/"


def build_checkout_url(provider, payment_id, amount_sum, return_url=None):
    """Provayderga qarab to'g'ri havolani qaytaradi."""
    if is_test_mode(provider):
        return test_checkout_url(payment_id)
    if provider == "payme":
        return payme_checkout_url(payment_id, amount_sum, return_url)
    if provider == "click":
        return click_checkout_url(payment_id, amount_sum, return_url)
    raise ValueError(f"Noma'lum provayder: {provider}")


# ---------------------------------------------------------------------------
# Imzo / autentifikatsiya tekshiruvi
# ---------------------------------------------------------------------------


def check_payme_auth(auth_header):
    """Payme `Authorization: Basic base64("Paycom:<key>")` yuboradi."""
    key = _env("PAYME_KEY")
    if not key:
        return False
    if not auth_header or not auth_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header[6:]).decode()
    except (ValueError, UnicodeDecodeError):
        return False
    _, _, provided = decoded.partition(":")
    # Vaqt bo'yicha xavfsiz solishtirish
    import hmac

    return hmac.compare_digest(provided, key)


def click_signature(*parts):
    """Click imzosi — barcha qismlarning md5 yig'indisi."""
    raw = "".join("" if p is None else str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


def check_click_signature(data, action):
    """Click `sign_string` ni tekshiradi.

    Prepare : click_trans_id + service_id + SECRET + merchant_trans_id +
              amount + action + sign_time
    Complete: click_trans_id + service_id + SECRET + merchant_trans_id +
              merchant_prepare_id + amount + action + sign_time
    """
    secret = _env("CLICK_SECRET_KEY")
    if not secret:
        return False

    parts = [
        data.get("click_trans_id"),
        data.get("service_id"),
        secret,
        data.get("merchant_trans_id"),
    ]
    if str(action) == "1":  # Complete
        parts.append(data.get("merchant_prepare_id"))
    parts += [data.get("amount"), data.get("action"), data.get("sign_time")]

    import hmac

    return hmac.compare_digest(click_signature(*parts), (data.get("sign_string") or "").lower())


# ---------------------------------------------------------------------------
# Payme JSON-RPC xatolari
# ---------------------------------------------------------------------------


class PaymeError:
    TRANSPORT = -32300
    ACCESS_DENIED = -32504
    METHOD_NOT_FOUND = -32601
    INVALID_AMOUNT = -31001
    ORDER_NOT_FOUND = -31050
    CANT_PERFORM = -31008
    TRANSACTION_NOT_FOUND = -31003


def payme_error(code, message, request_id=None, data=None):
    return {
        "error": {"code": code, "message": {"uz": message, "ru": message, "en": message}, "data": data},
        "id": request_id,
    }
