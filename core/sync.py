"""Mobil ilova foydalanuvchisini admin paneldagi `Member` yozuvi bilan sinxronlash.

Muammo: mobil ilovada ro'yxatdan o'tgan mijoz `users.User` (role=customer)
sifatida yaratilardi, admin panelning "Foydalanuvchilar" ro'yxati esa
`core.Member` dan o'qiydi. Ular o'zaro bog'lanmagani uchun yangi ro'yxatdan
o'tganlar admin panelda umuman ko'rinmasdi (`Member` faqat referal so'rovi
kelganda yaratilardi — `core/inbox.py` ga qarang).

Bu modul ikkalasini telefon raqami bo'yicha bog'laydi. Bog'lovchi maydon
(ForeignKey) qo'shilmadi — mavjud kod ham aynan telefon bo'yicha moslashtiradi,
shu uslub saqlab qolindi.
"""

import logging
import random
import re

from django.utils import timezone

from .models import ActivityStatus, Member, Status

logger = logging.getLogger(__name__)


def _digits(phone):
    return re.sub(r"\D", "", phone or "")


def _phone_key(phone):
    """Taqqoslash uchun kalit — oxirgi 9 ta raqam.

    Bazada formatlar aralash: "+998901234567" va "+998 90 123 45 67".
    """
    d = _digits(phone)
    return d[-9:] if len(d) >= 9 else d


def _gen_member_code():
    for _ in range(10):
        code = str(random.randint(100000000, 199999999))
        if not Member.objects.filter(member_code=code).exists():
            return code
    return str(random.randint(100000000, 999999999))


def build_phone_index():
    """Barcha `Member` larni telefon kaliti bo'yicha bir marta indekslaydi.

    Ko'p foydalanuvchini birdaniga sinxronlaganda (`sync_members` buyrug'i)
    har biri uchun alohida so'rov yubormaslik uchun.
    """
    index = {}
    for pk, phone in Member.objects.values_list("id", "phone"):
        key = _phone_key(phone)
        if key:
            index.setdefault(key, pk)
    return index


def find_member_by_phone(phone, index=None):
    """Telefon bo'yicha `Member` topadi (format har xil bo'lsa ham).

    `index` berilgan bo'lsa bazaga qo'shimcha so'rov yubormaydi.
    """
    key = _phone_key(phone)
    if not key:
        return None

    if index is not None:
        pk = index.get(key)
        return Member.objects.filter(pk=pk).first() if pk else None

    # Tez yo'l — aynan mos yozuv
    exact = Member.objects.filter(phone=phone).first()
    if exact:
        return exact

    # Formatlar har xil bo'lgani uchun: oxirgi 2 raqam bo'yicha toraytirib,
    # keyin raqamlar bo'yicha aniq solishtiramiz. Oxirgi 2 raqamdan keyin
    # hech qachon probel bo'lmaydi, shu sabab `endswith` ishonchli.
    for m in Member.objects.filter(phone__endswith=key[-2:]).only("id", "phone"):
        if _phone_key(m.phone) == key:
            return Member.objects.get(pk=m.pk)
    return None


def _status_from_membership(user):
    """`users.Membership` holatini admin paneldagi status'ga o'giradi."""
    membership = getattr(user, "membership", None)
    if membership is None:
        return None
    if membership.status == "active":
        return Status.PREMIUM
    if membership.status == "expired":
        return Status.OVERDUE
    return None


def sync_member_from_user(user, index=None):
    """Mijoz `User` uchun `Member` yozuvini yaratadi yoki yangilaydi.

    Telefon raqami bo'lmasa `None` qaytaradi — `Member` uchun telefon asosiy
    identifikator, usiz yozuv yaratishning ma'nosi yo'q.
    """
    # Import shu yerda — modul yuklanish tartibida aylanma bog'liqlik bo'lmasin
    from users.models import User

    if user.role != User.Role.CUSTOMER:
        return None

    phone = (user.phone_number or "").strip()
    if not phone:
        return None

    name = f"{user.first_name} {user.last_name}".strip()
    if not name:
        name = (user.email or "").split("@")[0] or phone

    member = find_member_by_phone(phone, index=index)
    created = member is None

    if created:
        joined = user.created_at.date() if getattr(user, "created_at", None) else timezone.now().date()
        member = Member(
            member_code=_gen_member_code(),
            phone=phone,
            city="Toshkent shahri",
            status=Status.NEW,
            activity_status=ActivityStatus.NEW,
            joined_at=joined,
        )

    member.name = name
    member.is_blocked = bool(getattr(user, "is_blocked", False))

    # Obuna holati bo'lsa status'ni shundan olamiz. Bo'lmasa — adminning
    # qo'lda qo'ygan statusini buzmaymiz.
    mapped = _status_from_membership(user)
    if mapped:
        member.status = mapped

    member.save()
    return member, created


def sync_member_safe(user):
    """Xato bo'lsa ham ro'yxatdan o'tishni to'xtatmaydigan variant."""
    try:
        return sync_member_from_user(user)
    except Exception:
        logger.exception("Member sinxronlashda xatolik (user=%s)", getattr(user, "pk", None))
        return None
