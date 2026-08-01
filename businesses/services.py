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
    tasdiqlash jarayoni baribir to'xtamaydi.
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

    try:
        return sms.get_provider().send(phone, text)
    except Exception:  # SMS xatosi tasdiqlashni to'xtatmasin
        import logging

        logging.getLogger(__name__).exception("Tasdiqlash SMS yuborilmadi (%s)", phone)
        return False


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

    try:
        return sms.get_provider().send(phone, text)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Kassir SMS yuborilmadi (%s)", phone)
        return False


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

    try:
        return sms.get_provider().send(phone, text)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Rad etish SMS yuborilmadi (%s)", phone)
        return False
