import uuid

from django.conf import settings
from django.db import models

from businesses.models import Business, Cashier


class DiscountChangeRequest(models.Model):
    """
    'Chegirmalar' -> 'Foiz o'zgartirish' -> So'rov -> Admin
    Biznes egasi chegirma foizini o'zgartirishni so'raydi, Admin tasdiqlaydi.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Ko'rib chiqilmoqda"
        APPROVED = "approved", "Tasdiqlangan"
        REJECTED = "rejected", "Rad etilgan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="discount_requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    old_percent = models.PositiveSmallIntegerField()
    new_percent = models.PositiveSmallIntegerField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_discount_requests",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business.name}: {self.old_percent}% -> {self.new_percent}%"


class DiscountUsage(models.Model):
    """
    Chegirma tarixi: Kim keldi, qachon, qancha (chegirma qo'llanilgan tranzaksiya).
    Kassir tomonidan ro'yxatga olinadi.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="discount_usages")
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="discount_usages"
    )
    cashier = models.ForeignKey(
        Cashier, on_delete=models.SET_NULL, blank=True, null=True, related_name="discount_usages"
    )
    applied_percent = models.PositiveSmallIntegerField()
    purchase_amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-used_at"]
        indexes = [models.Index(fields=["business", "used_at"])]

    def __str__(self):
        return f"{self.business.name} - {self.customer} - {self.used_at:%Y-%m-%d}"
