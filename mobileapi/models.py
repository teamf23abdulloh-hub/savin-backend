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


class RedeemCode(models.Model):
    """Kassaga QR o'rniga aytiladigan qisqa 4 xonali kod.

    QR ishlamasa mijoz shu kodni kassirga aytadi. Kod har 5 daqiqada
    yangilanadi va shu vaqt ichida FAOL kodlar orasida noyob bo'ladi —
    shuning uchun kassir uni bir qiymatga bog'lab bo'ladi. Telefon raqami
    o'rniga ishlatiladi (raqam maxfiyroq va o'zgarmas edi).
    """

    TTL_SECONDS = 5 * 60

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="redeem_code",
    )
    code = models.CharField(max_length=4, db_index=True)
    expires_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} -> {self.user_id}"

    @property
    def is_expired(self):
        from django.utils import timezone

        return timezone.now() >= self.expires_at

    @property
    def seconds_left(self):
        from django.utils import timezone

        left = (self.expires_at - timezone.now()).total_seconds()
        return int(left) if left > 0 else 0


class PhoneOtp(models.Model):
    """Telefon raqamini SMS kod bilan tasdiqlash.

    Kod ochiq saqlanmaydi — faqat xeshi. Har bir raqam uchun oxirgi
    tasdiqlanmagan yozuv ishlatiladi; muddat tugasa yoki urinishlar
    tugasa yaroqsiz bo'ladi.
    """

    MAX_ATTEMPTS = 5
    TTL_SECONDS = 5 * 60          # kod 5 daqiqa amal qiladi
    RESEND_COOLDOWN_SECONDS = 60  # qayta yuborish oralig'i

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=32, db_index=True)
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["phone", "-created_at"])]

    def __str__(self):
        return f"OTP {self.phone} ({'ishlatilgan' if self.is_used else 'faol'})"

    @property
    def is_expired(self):
        from django.utils import timezone

        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired and self.attempts < self.MAX_ATTEMPTS
