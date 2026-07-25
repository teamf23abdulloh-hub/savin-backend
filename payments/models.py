import uuid

from django.conf import settings
from django.db import models


class Payment(models.Model):
    """To'lovlar boshqaruvi: oylik daromad, muvaffaqiyatsiz to'lovlar, to'lov tarixi, export."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Muvaffaqiyatli"
        FAILED = "failed", "Muvaffaqiyatsiz"
        PENDING = "pending", "Kutilmoqda"
        REFUNDED = "refunded", "Qaytarilgan"

    class Provider(models.TextChoices):
        CLICK = "click", "Click"
        PAYME = "payme", "Payme"
        UZUM = "uzum", "Uzum Bank"
        CARD = "card", "Karta"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    provider = models.CharField(max_length=20, choices=Provider.choices)
    provider_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    failure_reason = models.TextField(blank=True, null=True)
    is_retry = models.BooleanField(default=False)
    original_payment = models.ForeignKey(
        "self", on_delete=models.SET_NULL, blank=True, null=True, related_name="retries"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.user} - {self.amount} - {self.status}"


class RefundRequest(models.Model):
    """Profilni ko'rish -> Refund tasdiqlash."""

    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        APPROVED = "approved", "Tasdiqlangan"
        REJECTED = "rejected", "Rad etilgan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="refund_requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_refunds",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund<{self.payment_id}:{self.status}>"
