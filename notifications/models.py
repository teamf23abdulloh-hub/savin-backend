import uuid

from django.conf import settings
from django.db import models

from businesses.models import Category


class PushNotification(models.Model):
    """
    Push Bildirishnomalar:
    Qabul qiluvchi tanlash -> Alohida foydalanuvchi / Kategoriya bo'yicha / Hammaga (global)
    Xabar yozish (UZ/RU/EN) -> Yuborish / Rejalashtirilgan yuborish
    """

    class Audience(models.TextChoices):
        SINGLE_USER = "single_user", "Alohida foydalanuvchi"
        CATEGORY = "category", "Kategoriya bo'yicha"
        ALL = "all", "Hammaga (global)"

    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        SCHEDULED = "scheduled", "Rejalashtirilgan"
        SENT = "sent", "Yuborilgan"
        FAILED = "failed", "Yuborilmadi"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications_created")

    audience = models.CharField(max_length=20, choices=Audience.choices)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="targeted_notifications",
    )
    target_category = models.ForeignKey(
        Category, on_delete=models.CASCADE, blank=True, null=True, related_name="notifications"
    )

    title_uz = models.CharField(max_length=255)
    title_ru = models.CharField(max_length=255, blank=True)
    title_en = models.CharField(max_length=255, blank=True)
    body_uz = models.TextField()
    body_ru = models.TextField(blank=True)
    body_en = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title_uz} ({self.audience})"


class UserNotification(models.Model):
    """Foydalanuvchi bildirishnomalar oynasi: 'Yangi mijoz', 'Chegirma', 'Eslatma'."""

    class NotificationType(models.TextChoices):
        NEW_CUSTOMER = "new_customer", "Yangi mijoz"
        DISCOUNT = "discount", "Chegirma"
        REMINDER = "reminder", "Eslatma"
        SYSTEM = "system", "Tizim"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_notifications")
    push_notification = models.ForeignKey(
        PushNotification, on_delete=models.SET_NULL, blank=True, null=True, related_name="deliveries"
    )
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices, default=NotificationType.SYSTEM)
    title = models.CharField(max_length=255)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"{self.title} -> {self.user}"
