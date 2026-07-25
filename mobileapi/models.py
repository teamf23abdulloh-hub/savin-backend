import uuid

from django.conf import settings
from django.db import models


class ReferralRequest(models.Model):
    """Mijoz 3 ta do'st taklif qilgach yuboradigan mukofot so'rovi.

    Bu so'rov admin panelning "So'rovlar" bo'limida ko'rinadi (admin backendga
    ko'prik orqali uzatiladi). Admin tasdiqласa mijoz a'zoligi 1 oyga uzayadi,
    rad etsa sabab bilan mijozga bildirishnoma boradi.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Ko'rib chiqilmoqda"
        APPROVED = "approved", "Tasdiqlangan"
        REJECTED = "rejected", "Rad etilgan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_requests",
    )
    invited_count = models.PositiveIntegerField(default=3)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reason = models.TextField(blank=True)  # rad etilganda sabab
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ReferralRequest<{self.customer_id}:{self.status}>"


class CustomerNotification(models.Model):
    """Mijozga (mobil ilova foydalanuvchisiga) yuboriladigan bildirishnoma."""

    class Kind(models.TextChoices):
        GENERAL = "general", "Umumiy"
        DISCOUNT = "discount", "Chegirma"
        REFERRAL = "referral", "Referal"
        MEMBERSHIP = "membership", "A'zolik"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_notifications",
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.GENERAL)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} -> {self.user_id}"
