"""Mobil ilova domeni — view'lardan tashqarida ishlatiladigan mantiq."""

from django.utils import timezone

from users.models import Membership

from .models import CustomerNotification, ReferralRequest


class ReferralReviewError(Exception):
    """So'rov topilmadi / allaqachon ko'rib chiqilgan / action noto'g'ri."""


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
        CustomerNotification.objects.create(
            user=user,
            title="Referal so'rovi rad etildi",
            body=reason or "So'rovingiz rad etildi.",
            kind=CustomerNotification.Kind.REFERRAL,
        )
    else:
        raise ReferralReviewError("Noto'g'ri action.")

    return ref
