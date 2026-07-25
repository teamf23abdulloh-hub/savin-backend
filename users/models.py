import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPERADMIN = "superadmin", "Super Admin"
        ADMIN = "admin", "Admin"
        BUSINESS_OWNER = "business_owner", "Biznes egasi"
        CASHIER = "cashier", "Kassir"
        CUSTOMER = "customer", "Mijoz"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    # 2FA (ixtiyoriy)
    is_2fa_enabled = models.BooleanField(default=False)
    two_fa_secret = models.CharField(max_length=64, blank=True, null=True)

    # Bloklash (foydalanuvchi boshqaruvi)
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen_at = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} ({self.role})"


class Membership(models.Model):
    """Foydalanuvchi profilidagi 'membership' - obuna holati (Admin panelda ko'rinadi)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Faol"
        EXPIRED = "expired", "Muddati tugagan"
        CANCELLED = "cancelled", "Bekor qilingan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="membership")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Membership<{self.user.email}:{self.status}>"


class UserActivityLog(models.Model):
    """DAU/MAU va foydalanuvchi tarixi uchun."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activity_logs")
    action = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]
