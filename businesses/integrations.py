"""Platforma -> admin panel yo'nalishi (ichki ko'prik).

Landing'da ariza yakunlanganda yoki biznes egasi chegirma foizini o'zgartirishni
so'raganda, hodisa admin panelning o'z modellariga (`core`) yoziladi — shunda u
admin panelning "Arizalar" / "So'rovlar" bo'limlarida va qo'ng'iroq (bell)
bildirishnomasida ko'rinadi.

Ilgari admin panel alohida backend edi va bu yerdan unga HTTP webhook
yuborilardi. Endi ikkalasi bitta jarayonda — to'g'ridan-to'g'ri funksiya
chaqiriladi. Chaqiruv baribir best-effort: admin tomonda xato bo'lsa ham
arizaning asosiy oqimi buzilmasligi kerak.
"""

import logging

logger = logging.getLogger(__name__)


# Platforma kategoriyalari erkin (Category modeli), admin panel esa qat'iy enum
# (BusinessCategory) ishlatadi. Ariza admin tomonda validatsiyadan o'tishi uchun
# kalit so'z bo'yicha eng mos kategoriyaga moslaymiz.
_ADMIN_CATEGORY_BY_KEYWORD = [
    (("restoran", "restaurant", "ovqat", "milliy taom"), "Restoran"),
    (("kafe", "cafe", "coffee", "qahva"), "Kafe"),
    (("fitnes", "fitness", "sport", "gym", "sportzal"), "Fitness"),
    (("barber", "sartarosh", "soch"), "Barber"),
    (("salon", "go'zallik", "gozallik", "beauty", "spa", "manikur"), "Salon"),
    (("avto", "moshina", "avtomobil", "car", "avtomoyka"), "Avto"),
    (("tibbiyot", "med", "klinika", "stomatolog", "shifo"), "Tibbiyot"),
    (("shifoxona", "hospital", "kasalxona"), "Shifoxona"),
    (("ta'lim", "talim", "o'quv", "oquv", "kurs", "school", "maktab"), "Ta'lim"),
    (("taxi", "taksi"), "Taxi"),
]
_ADMIN_CATEGORY_DEFAULT = "Restoran"


def _map_category(name: str) -> str:
    """Platforma kategoriya nomini admin panel BusinessCategory qiymatiga o'giradi."""
    text = (name or "").strip().lower()
    for keywords, admin_value in _ADMIN_CATEGORY_BY_KEYWORD:
        if any(kw in text for kw in keywords):
            return admin_value
    return _ADMIN_CATEGORY_DEFAULT


def forward_application_to_admin_panel(application) -> bool:
    """Arizani admin panelning "Arizalar" bo'limiga chiqaradi.

    Muvaffaqiyatli bo'lsa True, xato bo'lsa False qaytaradi — chaqiruvchi hech
    qachon bu natijaga bog'lanmasligi kerak.
    """
    from core.inbox import receive_business_application

    category_name = application.category.name if application.category_id else ""
    work_hours = ""
    if application.work_hours_from and application.work_hours_to:
        work_hours = (
            f"{application.work_hours_from:%H:%M} - "
            f"{application.work_hours_to:%H:%M}"
        )
    payload = {
        # source_id — platformadagi ariza ID'si. Admin panel tasdiqlash/rad
        # etish natijasini shu ID bilan qaytaradi (core/bridge.py) — shunda
        # platformada ham User/Business yaratiladi.
        "source_id": str(application.id),
        "business_name": application.business_name,
        "category": _map_category(category_name),
        "phone": application.phone_number,
        # region admin tomonda erkin matn — o'qiladigan label yuboramiz.
        "region": application.get_region_display(),
        "discount_percent": int(application.discount_percent or 0),
        # Ariza tafsiloti (admin paneldagi to'liq ko'rinish uchun)
        "responsible_name": application.responsible_full_name,
        "business_type": application.get_business_type_display(),
        "description": application.short_description,
        "email": application.email,
        "instagram": application.instagram,
        "telegram": application.telegram,
        "website": application.website,
        "district": application.city_district,
        "address": application.full_address,
        "work_days": application.get_work_days_display(),
        "work_hours": work_hours,
        # Admin tomonda min_purchase decimal_places=0 — kasr yuborilsa
        # validatsiyadan o'tmaydi, shuning uchun butun songa keltiramiz.
        "min_purchase": str(int(application.min_purchase_amount or 0)),
        "discount_scope": application.get_discount_type_display(),
        "login": application.panel_login,
        "password": application.panel_password,
        # Biznes egasi xaritada belgilagan lokatsiya — admin panel detail
        # oynasidagi xaritada ko'rsatiladi.
        "latitude": str(application.latitude) if application.latitude is not None else None,
        "longitude": str(application.longitude) if application.longitude is not None else None,
    }

    try:
        receive_business_application(payload)
    except Exception as exc:  # noqa: BLE001 — ariza oqimi buzilmasin
        logger.warning("Admin panelga ariza uzatilmadi: %s", exc)
        return False
    return True


def notify_admin_panel_business_event(business, title, body="", extra=None):
    """Biznes panelidagi hodisani (masalan chegirma foizini o'zgartirish
    so'rovi) admin panel qo'ng'irog'iga (bell) chiqaradi — bildirishnoma
    bosilganda o'sha biznes detail sahifasi ochiladi.

    `extra` — qo'shimcha maydonlar (masalan so'rov tafsiloti: kind,
    request_id, old/new foiz) — admin panel "So'rovlar" bo'limi uchun.
    """
    from core.inbox import receive_business_event

    payload = {
        "title": title,
        "body": body,
        # Admin tomonda biznesni topish uchun kalitlar
        "business_login": business.owner.email if business.owner_id else "",
        "business_name": business.name,
    }
    if extra:
        payload.update(extra)

    try:
        receive_business_event(payload)
    except Exception as exc:  # noqa: BLE001 — asosiy oqim buzilmasin
        logger.warning("Admin panelga bildirishnoma uzatilmadi: %s", exc)
        return False
    return True
