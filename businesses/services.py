"""Ariza tasdiqlash/rad etish biznes-logikasi.

Bu logika ikki joydan chaqiriladi:
1. AdminApplicationReviewView — o'z API'miz orqali (JWT admin).
2. AdminBridgeApplicationReviewView — alohida admin panel backendi arizani
   tasdiqlab/rad etib, natijani bizga qaytarganda (token bilan himoyalangan
   ochiq endpoint).

Shuning uchun umumiy funksiyalarga ajratilgan — ikkala yo'l ham bir xil
natija beradi (User yaratish, Business yaratish, bildirishnoma).
"""

from django.utils import timezone

from businesses.default_services import create_default_services

from businesses.models import Application, Business
from notifications.models import UserNotification
from users.models import User


class ApplicationApproveError(Exception):
    """Tasdiqlashda foydalanuvchiga ko'rsatiladigan xato."""


def _ensure_owner_user(application):
    """Ariza uchun biznes egasi hisobini topadi yoki yaratadi.

    Ustuvorlik: arizada ko'rsatilgan panel_login (+parol) — biznes egasi
    landing'da o'zi tanlagan kirish ma'lumotlari. Bo'lmasa ariza emaili.
    """
    if application.applicant is not None and not application.panel_login:
        return application.applicant

    login_email = (application.panel_login or "").strip().lower()
    fallback_email = (application.email or "").strip().lower()
    email = login_email or fallback_email
    if not email:
        raise ApplicationApproveError(
            "Arizada login/email ko'rsatilmagan — biznes egasi hisobini "
            "yaratib bo'lmaydi."
        )

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User(
            username=email,
            email=email,
            phone_number=application.phone_number,
            role=User.Role.BUSINESS_OWNER,
        )
        if application.panel_password:
            user.set_password(application.panel_password)
        else:
            user.set_unusable_password()
        user.save()
    elif application.panel_password and not user.has_usable_password():
        # Hisob avval parolsiz yaratilgan bo'lsa, arizadagi parol beriladi.
        user.set_password(application.panel_password)
        user.save(update_fields=["password"])
    return user


def approve_application(application, reviewer=None):
    """Arizani tasdiqlaydi: User (kerak bo'lsa) + Business yaratadi.

    Muvaffaqiyatda Business obyektini qaytaradi.
    Xatoda ApplicationApproveError ko'taradi.
    """
    application.reviewed_by = reviewer
    application.reviewed_at = timezone.now()

    owner = _ensure_owner_user(application)
    application.applicant = owner
    application.status = Application.Status.APPROVED
    application.save()

    business, _created = Business.objects.get_or_create(
        application=application,
        defaults=dict(
            owner=owner,
            name=application.business_name,
            category=application.category,
            business_type=application.business_type,
            description=application.short_description,
            phone_number=application.phone_number,
            email=application.email,
            instagram=application.instagram,
            telegram=application.telegram,
            website=application.website,
            region=application.region,
            city_district=application.city_district,
            full_address=application.full_address,
            latitude=application.latitude,
            longitude=application.longitude,
            is_active=True,
        ),
    )
    if owner.role != User.Role.BUSINESS_OWNER:
        owner.role = User.Role.BUSINESS_OWNER
        owner.save(update_fields=["role"])

    # Kategoriyaga mos standart xizmatlar — busiz kassir QR skanerlagach
    # 4-qadamda "xizmat turi"ni tanlay olmaydi. Egasi ularni keyin
    # o'z panelida tahrirlashi mumkin.
    create_default_services(business)

    # Landing arizasida kiritilgan chegirma "Chegirmalar" sahifasida darhol
    # karta bo'lib ko'rinishi uchun Standart chegirmani yaratamiz (ilgari u
    # faqat shartnoma foizi sifatida qolib, kartalar ro'yxatida chiqmasdi).
    _create_default_discount(business, application)

    UserNotification.objects.create(
        user=owner,
        notification_type=UserNotification.NotificationType.SYSTEM,
        title="Ariza tasdiqlandi",
        body=(
            f"{application.business_name} bo'yicha arizangiz tasdiqlandi — "
            "hamkorlik faollashtirildi."
        ),
    )

    # Biznes egasiga SMS: tasdiqlangani va panel havolasi
    send_business_decision_sms(business, approved=True)

    return business


# ---------------------------------------------------------------------------
# Profil o'zgartirish so'rovlari (biznes egasi -> admin tasdiqlaydi)
# ---------------------------------------------------------------------------

_PROFILE_FIELD_LABELS = {
    "name": "Biznes nomi",
    "description": "Tavsif",
    "full_address": "Manzil",
    "phone_number": "Telefon",
    "email": "Email",
    "work_hours_from": "Ochilish vaqti",
    "work_hours_to": "Yopilish vaqti",
}


def profile_request_body(changes):
    """O'zgarishlarni admin o'qishi uchun qisqa matnga aylantiradi."""
    parts = []
    for field, value in changes.items():
        label = _PROFILE_FIELD_LABELS.get(field, field)
        parts.append(f"{label}: {value}")
    return "; ".join(parts) if parts else "O'zgarish yo'q"


def _parse_time(value):
    """"HH:MM" -> datetime.time (bo'sh/xato bo'lsa None)."""
    from datetime import datetime

    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def apply_profile_review(change_request, action, reject_reason=""):
    """Profil o'zgartirish so'rovini tasdiqlaydi/rad etadi.

    Tasdiqlanganda o'zgarishlar `Business`ga (ish vaqti esa `Application`ga)
    qo'llanadi. Ikkala holatda ham biznes egasiga bildirishnoma boradi.
    """
    business = change_request.business
    changes = change_request.changes or {}

    if action == "approve":
        biz_fields = []
        for field in ("name", "description", "full_address", "phone_number", "email"):
            if field in changes:
                setattr(business, field, changes[field])
                biz_fields.append(field)
        if biz_fields:
            business.save(update_fields=biz_fields)

        # Ish vaqti Application'da
        app = business.application
        if app and ("work_hours_from" in changes or "work_hours_to" in changes):
            if "work_hours_from" in changes:
                app.work_hours_from = _parse_time(changes["work_hours_from"])
            if "work_hours_to" in changes:
                app.work_hours_to = _parse_time(changes["work_hours_to"])
            app.save(update_fields=["work_hours_from", "work_hours_to"])

        change_request.status = change_request.Status.APPROVED
        title = "Profil o'zgarishi tasdiqlandi"
        body = "So'ralgan profil o'zgarishlari qo'llandi: " + profile_request_body(changes)
    else:
        change_request.status = change_request.Status.REJECTED
        change_request.reason = reject_reason or ""
        title = "Profil o'zgarishi rad etildi"
        body = "Profil o'zgartirish so'rovingiz rad etildi."
        if reject_reason:
            body += f" Sabab: {reject_reason}"

    change_request.reviewed_at = timezone.now()
    change_request.save()

    from notifications.models import UserNotification

    UserNotification.objects.create(
        user=change_request.requested_by,
        notification_type=UserNotification.NotificationType.SYSTEM,
        title=title,
        body=body,
    )
    return change_request


def _create_default_discount(business, application):
    """Ariza foizidan Standart chegirma kartasini yaratadi (bo'lmasa).

    Import funksiya ichida — `businesses` yuklanayotganda `discounts` hali
    tayyor bo'lmasligi mumkin.
    """
    from discounts.models import Discount

    percent = int(application.discount_percent or 0)
    if percent < 1:
        return
    Discount.objects.get_or_create(
        business=business,
        category=Discount.Category.STANDARD,
        defaults=dict(
            description=application.get_discount_type_display() or "Barcha xaridlar uchun",
            percent=min(percent, 100),
            min_purchase=application.min_purchase_amount or 0,
            is_active=True,
        ),
    )


def reject_application(application, reason="", reviewer=None):
    """Arizani rad etadi (sabab bilan) va ariza egasiga bildirishnoma beradi."""
    application.reviewed_by = reviewer
    application.reviewed_at = timezone.now()
    application.status = Application.Status.REJECTED
    application.rejection_reason = reason or ""
    application.save()

    if application.applicant:
        UserNotification.objects.create(
            user=application.applicant,
            notification_type=UserNotification.NotificationType.SYSTEM,
            title="Ariza rad etildi",
            body=(
                f"{application.business_name} bo'yicha arizangiz rad etildi. "
                + (f"Sabab: {reason}" if reason else "")
            ),
        )

    # Ariza egasiga SMS: rad etilgani va sababi
    send_application_rejected_sms(application, reason=reason)

    return application


# ---------------------------------------------------------------------------
# SMS xabarnomalar
# ---------------------------------------------------------------------------


def _panel_url():
    """Biznes/kassir panelining manzili."""
    import os

    return (
        os.environ.get("BUSINESS_PANEL_URL")
        or "https://savin-biznes-kassir.vercel.app"
    ).rstrip("/")


def send_business_decision_sms(business, approved=True):
    """Biznes tasdiqlanganda egasiga SMS yuboradi (panel havolasi bilan).

    SMS provayder ulanmagan bo'lsa (test rejimi) xabar faqat logga yoziladi —
    tasdiqlash jarayoni baribir to'xtamaydi. `sms.send_sms` istisno
    ko'tarmaydi, xatoni logga yozib `False` qaytaradi.
    """
    from mobileapi import sms

    phone = (business.phone_number or "").strip()
    if not phone and business.owner_id:
        phone = (business.owner.phone_number or "").strip()
    if not phone:
        return False

    login = business.owner.email if business.owner_id else ""
    text = (
        f"Savin: \"{business.name}\" biznesingiz tasdiqlandi! "
        f"Panelga kiring: {_panel_url()} "
        + (f"Login: {login}" if login else "")
    ).strip()

    return sms.send_sms(phone, text)


def send_cashier_created_sms(cashier, password=""):
    """Kassir qo'shilganda unga kirish ma'lumotlarini SMS bilan yuboradi."""
    from mobileapi import sms

    phone = (cashier.phone or "").strip()
    if not phone:
        return False

    text = (
        f"Savin: siz \"{cashier.business.name}\" kassiri sifatida qo'shildingiz. "
        f"Panel: {_panel_url()} Login: {cashier.login}"
        + (f" Parol: {password}" if password else "")
    )

    return sms.send_sms(phone, text)


def send_application_rejected_sms(application, reason=""):
    """Ariza rad etilganda ariza egasiga SMS yuboradi."""
    from mobileapi import sms

    phone = (application.phone_number or "").strip()
    if not phone and application.applicant_id:
        phone = (application.applicant.phone_number or "").strip()
    if not phone:
        return False

    text = (
        f"Savin: \"{application.business_name}\" bo'yicha arizangiz rad etildi."
        + (f" Sabab: {reason}" if reason else "")
        + " Savollar bo'lsa: @savin_biznes"
    )

    return sms.send_sms(phone, text)
