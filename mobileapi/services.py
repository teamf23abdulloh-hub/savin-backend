"""Mobil ilova domeni — view'lardan tashqarida ishlatiladigan mantiq."""

import re
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from users.models import Membership

from .models import (
    CustomerNotification,
    ReferralCode,
    ReferralInvite,
    ReferralRequest,
)

# Taklif havolasi. Landing sayti `/i/<KOD>` sahifasi ilovani ochadi,
# ilova o'rnatilmagan bo'lsa Play Marketga yo'naltiradi.
REFERRAL_LINK_BASE = getattr(settings, "REFERRAL_LINK_BASE", "https://savin.uz/i")
ANDROID_PACKAGE = getattr(settings, "ANDROID_PACKAGE", "com.iqbolmadaliyev.savin")

# Mukofot uchun kerakli FAOL do'stlar soni
REWARD_FRIENDS_REQUIRED = 3


class ReferralReviewError(Exception):
    """So'rov topilmadi / allaqachon ko'rib chiqilgan / action noto'g'ri."""


class ReferralError(Exception):
    """Taklif kodini biriktirishda yoki mukofot so'rashda yuz bergan xato."""


# ---------------------------------------------------------------- taklif kodi


def _code_seed(user):
    """Kodning harfli qismi — ismdan (dizayndagi "AZIZ2026" kabi)."""
    name = (user.first_name or user.username or "SAVIN").upper()
    letters = re.sub(r"[^A-Z]", "", name)
    if len(letters) < 4:
        letters = (letters + "SAVIN")[:4]
    return letters[:4]


def get_referral_code(user):
    """Foydalanuvchining taklif kodi (bo'lmasa yaratiladi)."""
    existing = ReferralCode.objects.filter(user=user).first()
    if existing:
        return existing

    seed = _code_seed(user)
    for _ in range(30):
        code = f"{seed}{secrets.randbelow(9000) + 1000}"
        if ReferralCode.objects.filter(code=code).exists():
            continue
        try:
            return ReferralCode.objects.create(user=user, code=code)
        except IntegrityError:
            continue  # poyga holati — qayta urinamiz
    # Deyarli imkonsiz: baribir noyob kod beramiz
    return ReferralCode.objects.create(user=user, code=secrets.token_hex(6).upper())


def referral_link(code):
    return f"{REFERRAL_LINK_BASE}/{code}"


def attach_referral(invitee, raw_code):
    """Yangi foydalanuvchini taklif qilgan kishiga biriktiradi.

    Qaytaradi: yaratilgan `ReferralInvite` yoki `None` (kod bo'sh/noto'g'ri,
    o'zini o'zi taklif qilish, yoki foydalanuvchi allaqachon biriktirilgan).
    Ro'yxatdan o'tish oqimini buzmasligi uchun xato ko'tarmaydi.
    """
    code = (raw_code or "").strip().upper()
    if not code:
        return None
    if ReferralInvite.objects.filter(invitee=invitee).exists():
        return None

    owner = ReferralCode.objects.filter(code=code).select_related("user").first()
    if owner is None or owner.user_id == invitee.id:
        return None

    with transaction.atomic():
        invite = ReferralInvite.objects.create(
            inviter=owner.user,
            invitee=invitee,
            code_used=code,
        )

    CustomerNotification.objects.create(
        user=owner.user,
        title="Do'stingiz ro'yxatdan o'tdi 🎉",
        body=(
            f"{invitee.get_full_name() or 'Yangi do\'stingiz'} taklifingiz orqali qo'shildi. "
            f"U {ReferralInvite.ACTIVE_DAYS_REQUIRED} kun ilovaga kirsa taklif to'liq hisoblanadi."
        ),
        kind=CustomerNotification.Kind.REFERRAL,
    )
    return invite


def record_activity(user):
    """Foydalanuvchi ilovaga kirdi — faollik kunini belgilaydi.

    Kunига faqat BIR marta hisoblanadi. 7 kunga yetganda taklif "Aktiv"
    bo'ladi va taklif qilgan kishiga bildirishnoma boradi.
    """
    now = timezone.now()
    today = timezone.localdate()

    # Umumiy "oxirgi ko'rinish" — admin paneldagi faollik uchun
    if user.last_seen_at is None or user.last_seen_at.date() != today:
        user.last_seen_at = now
        user.save(update_fields=["last_seen_at"])

    invite = ReferralInvite.objects.filter(invitee=user).first()
    if invite is None or invite.status == ReferralInvite.Status.ACTIVE:
        return invite
    if invite.last_active_date == today:
        return invite

    invite.active_days += 1
    invite.last_active_date = today
    fields = ["active_days", "last_active_date"]

    if invite.active_days >= ReferralInvite.ACTIVE_DAYS_REQUIRED:
        invite.status = ReferralInvite.Status.ACTIVE
        invite.activated_at = now
        fields += ["status", "activated_at"]
        CustomerNotification.objects.create(
            user=invite.inviter,
            title="Do'stingiz faollashdi ✅",
            body=(
                f"{user.get_full_name() or 'Do\'stingiz'} bir hafta davomida ilovadan "
                "foydalandi — taklif to'liq hisoblandi."
            ),
            kind=CustomerNotification.Kind.REFERRAL,
        )

    invite.save(update_fields=fields)
    return invite


def _friend_row(invite):
    invitee = invite.invitee
    phone = invitee.phone_number or ""
    return {
        "id": str(invite.id),
        "name": invitee.get_full_name() or invitee.username or "Do'st",
        "phone": phone,
        "status": invite.status,
        "active_days": invite.active_days,
        "days_left": invite.days_left,
        "required_days": ReferralInvite.ACTIVE_DAYS_REQUIRED,
        "joined_at": invite.created_at.isoformat(),
        "last_active_date": (
            invite.last_active_date.isoformat() if invite.last_active_date else None
        ),
    }


def referral_overview(user):
    """Referal ekrani uchun to'liq ma'lumot."""
    code_obj = get_referral_code(user)
    invites = list(
        ReferralInvite.objects.filter(inviter=user).select_related("invitee")
    )

    friends = [_friend_row(i) for i in invites]
    active = [i for i in invites if i.status == ReferralInvite.Status.ACTIVE]
    # Mukofotga hali kiritilmagan faol do'stlar
    unclaimed = [i for i in active if i.reward_request_id is None]

    last_request = ReferralRequest.objects.filter(customer=user).first()

    return {
        "code": code_obj.code,
        "link": referral_link(code_obj.code),
        "invited_count": len(invites),
        "active_count": len(active),
        "pending_count": len(invites) - len(active),
        "required_days": ReferralInvite.ACTIVE_DAYS_REQUIRED,
        "reward_required": REWARD_FRIENDS_REQUIRED,
        "progress": min(len(unclaimed), REWARD_FRIENDS_REQUIRED),
        "remaining_for_reward": max(0, REWARD_FRIENDS_REQUIRED - len(unclaimed)),
        "bonus_days": (len(active) // REWARD_FRIENDS_REQUIRED) * 30,
        "can_request": len(unclaimed) >= REWARD_FRIENDS_REQUIRED
        and not (last_request and last_request.status == ReferralRequest.Status.PENDING),
        "request_status": last_request.status if last_request else None,
        "request_reason": last_request.reason if last_request else "",
        "friends": friends,
    }


def create_reward_request(user):
    """3 ta FAOL do'st yig'ilganda adminga 1 oylik obuna arizasini yuboradi."""
    unclaimed = list(
        ReferralInvite.objects.filter(
            inviter=user,
            status=ReferralInvite.Status.ACTIVE,
            reward_request__isnull=True,
        ).order_by("activated_at")
    )
    if len(unclaimed) < REWARD_FRIENDS_REQUIRED:
        raise ReferralError(
            f"Ariza yuborish uchun {REWARD_FRIENDS_REQUIRED} ta faol do'st kerak. "
            f"Hozir {len(unclaimed)} ta."
        )

    pending = ReferralRequest.objects.filter(
        customer=user, status=ReferralRequest.Status.PENDING
    ).first()
    if pending:
        raise ReferralError("Avvalgi arizangiz hali ko'rib chiqilmoqda.")

    with transaction.atomic():
        req = ReferralRequest.objects.create(
            customer=user, invited_count=REWARD_FRIENDS_REQUIRED
        )
        ids = [i.id for i in unclaimed[:REWARD_FRIENDS_REQUIRED]]
        ReferralInvite.objects.filter(id__in=ids).update(reward_request=req)
    return req


def review_referral_request(request_id, action, reason=""):
    """Referal mukofot so'rovini tasdiqlaydi yoki rad etadi.

    Tasdiqlansa mijoz a'zoligi +1 oyga uzayadi va mijozga bildirishnoma boradi;
    rad etilsa — sabab bilan bildirishnoma boradi.

    Ikki joydan chaqiriladi: admin panelning "Referal so'rovlari" bo'limi
    (`core.bridge`) va eski public bridge endpointi.
    """
    reason = (reason or "").strip()

    try:
        ref = ReferralRequest.objects.select_related("customer").get(id=request_id)
    except (ReferralRequest.DoesNotExist, ValueError, TypeError):
        raise ReferralReviewError("So'rov topilmadi.")

    if ref.status != ReferralRequest.Status.PENDING:
        raise ReferralReviewError("Allaqachon ko'rib chiqilgan.")

    user = ref.customer
    if action == "approve":
        membership, _ = Membership.objects.get_or_create(user=user)
        now = timezone.now()
        base = (
            membership.expires_at
            if membership.expires_at and membership.expires_at > now
            else now
        )
        membership.expires_at = base + timezone.timedelta(days=30)
        membership.status = Membership.Status.ACTIVE
        membership.save()
        ref.status = ReferralRequest.Status.APPROVED
        ref.reviewed_at = now
        ref.save(update_fields=["status", "reviewed_at"])
        CustomerNotification.objects.create(
            user=user,
            title="Referal mukofoti tasdiqlandi 🎉",
            body="Do'stlaringizni taklif qilganingiz uchun a'zolik +1 oyga uzaytirildi!",
            kind=CustomerNotification.Kind.REFERRAL,
        )
    elif action == "reject":
        ref.status = ReferralRequest.Status.REJECTED
        ref.reason = reason
        ref.reviewed_at = timezone.now()
        ref.save(update_fields=["status", "reason", "reviewed_at"])
        # Rad etilgan bo'lsa do'stlar "band" bo'lib qolmasin — foydalanuvchi
        # qayta ariza yubora olishi kerak.
        ReferralInvite.objects.filter(reward_request=ref).update(reward_request=None)
        CustomerNotification.objects.create(
            user=user,
            title="Referal so'rovi rad etildi",
            body=reason or "So'rovingiz rad etildi.",
            kind=CustomerNotification.Kind.REFERRAL,
        )
    else:
        raise ReferralReviewError("Noto'g'ri action.")

    return ref
