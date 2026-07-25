"""Admin panel tomoni: platformadan keladigan hodisalarni qabul qilish.

Ilgari bu mantiq `core/views.py` dagi public endpointlar ichida edi va asosiy
backend (savin_django) ularga HTTP POST qilardi. Endi ikkala tizim bitta
jarayonda bo'lgani uchun `businesses` / `mobileapi` shu funksiyalarni
to'g'ridan-to'g'ri chaqiradi — tarmoq so'rovi, timeout va "admin backend
o'chiq" holati umuman yo'q.

Public HTTP endpointlar ham joyida qoldi (`/api/public/...`) — ular endi shu
funksiyalarning ustidagi yupqa qatlam.
"""

import random

from django.utils import timezone

from .models import (
    ActivityStatus,
    AdminAlert,
    AdminAlertKind,
    ApplicationStatus,
    Business,
    BusinessRequest,
    Member,
    ReferralRequest,
    Status,
)
from .serializers import LandingBusinessApplicationSerializer


def _gen_member_code():
    for _ in range(10):
        code = str(random.randint(100000000, 199999999))
        if not Member.objects.filter(member_code=code).exists():
            return code
    return str(random.randint(100000000, 999999999))


def receive_business_application(payload):
    """Landing'dan kelgan biznes arizasini admin panel bazasiga yozadi.

    Ariza "Arizalar" bo'limida va qo'ng'iroq (bell) bildirishnomasida ko'rinadi.
    Ma'lumot noto'g'ri bo'lsa `serializers.ValidationError` ko'tariladi.
    """
    serializer = LandingBusinessApplicationSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    app = serializer.save(status=ApplicationStatus.NEW, created_at=timezone.now())
    AdminAlert.objects.create(
        kind=AdminAlertKind.BUSINESS_APPLICATION,
        title="Yangi biznes arizasi",
        body=f"{app.business_name} landing saytdan ariza yubordi",
    )
    return app


def receive_business_event(payload):
    """Biznes panelidagi hodisani (masalan chegirma foizini o'zgartirish
    so'rovi) admin panel qo'ng'irog'iga chiqaradi.

    `(alert, business)` juftligini qaytaradi; `title` bo'sh bo'lsa `ValueError`.
    """
    title = (payload.get("title") or "").strip()
    body = (payload.get("body") or "").strip()
    if not title:
        raise ValueError("title majburiy")

    # Admin-tomondagi Business'ni topish: avval panel logini bo'yicha
    # (eng ishonchli — unikal), topilmasa nomi bo'yicha.
    business = None
    login = (payload.get("business_login") or "").strip()
    name = (payload.get("business_name") or "").strip()
    if login:
        business = Business.objects.filter(login__iexact=login).order_by("-id").first()
    if business is None and name:
        business = Business.objects.filter(name__iexact=name).order_by("-id").first()

    alert = AdminAlert.objects.create(
        kind=AdminAlertKind.BUSINESS_REQUEST,
        title=title,
        body=body,
        business=business,
    )

    # So'rov tafsiloti kelgan bo'lsa (masalan chegirma foizini o'zgartirish)
    # biznes detail sahifasining "So'rovlar" bo'limi uchun yozib qo'yamiz.
    request_id = (payload.get("request_id") or "").strip()
    if business is not None and request_id:
        BusinessRequest.objects.get_or_create(
            source_id=request_id,
            defaults=dict(
                business=business,
                kind=payload.get("kind", "discount_request"),
                title=title,
                body=body,
                old_percent=int(payload.get("old_percent") or 0),
                new_percent=int(payload.get("new_percent") or 0),
                reason=payload.get("reason", ""),
            ),
        )

    return alert, business


def receive_referral_request(payload):
    """Mijozning referal mukofot so'rovini admin panelga chiqaradi.

    So'rov "Referal so'rovlari" bo'limida va qo'ng'iroqda ko'rinadi.
    `source_id` bo'sh bo'lsa `ValueError`.
    """
    source_id = (payload.get("source_id") or "").strip()
    member_name = (payload.get("member_name") or "").strip() or "Mijoz"
    member_phone = (payload.get("member_phone") or "").strip()
    if not source_id:
        raise ValueError("source_id majburiy")
    try:
        invited = int(payload.get("invited_count") or 3)
    except (TypeError, ValueError):
        invited = 3

    # So'rov shu foydalanuvchining "Foydalanuvchilar" sahifasida ko'rinishi
    # uchun Member yozuvini topamiz yoki yaratamiz (telefon bo'yicha).
    member = None
    if member_phone:
        member = Member.objects.filter(phone=member_phone).first()
    if member is None:
        member = Member.objects.create(
            member_code=_gen_member_code(),
            name=member_name,
            phone=member_phone,
            city="Toshkent",
            status=Status.NEW,
            activity_status=ActivityStatus.ACTIVE,
            joined_at=timezone.now().date(),
            referral_invited=invited,
        )

    req, _ = ReferralRequest.objects.get_or_create(
        source_id=source_id,
        defaults=dict(
            member=member,
            member_name=member_name,
            member_phone=member_phone,
            invited_count=invited,
        ),
    )
    AdminAlert.objects.create(
        kind=AdminAlertKind.REFERRAL_REQUEST,
        title="Yangi referal mukofot so'rovi",
        body=f"{member_name} {invited} ta do'st taklif qildi — mukofot so'rayapti",
    )
    return req
