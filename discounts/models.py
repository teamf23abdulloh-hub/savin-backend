import uuid

from django.conf import settings
from django.db import models

from businesses.models import Business, Cashier


class Discount(models.Model):
    """Biznesning chegirma turlari ("Chegirmalar" sahifasidagi kartalar).

    Bitta biznesda bir nechta chegirma bo'lishi mumkin (Standart, Premium,
    VIP...). Har biri alohida foiz, minimal xarid va faollik holatiga ega.
    Biznes egasi ularni o'z panelida qo'shadi/tahrirlaydi/o'chiradi.
    """

    class Category(models.TextChoices):
        STANDARD = "Standart", "Standart"
        PREMIUM = "Premium", "Premium"
        SPECIAL = "Maxsus taklif", "Maxsus taklif"
        VIP = "VIP", "VIP"
        BIRTHDAY = "Tug'ilgan kun", "Tug'ilgan kun"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="discounts")
    category = models.CharField(max_length=32, choices=Category.choices)
    description = models.CharField(max_length=255, blank=True)
    percent = models.PositiveSmallIntegerField()
    min_purchase = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    is_active = models.BooleanField(default=True)
    # Necha marta qo'llanilgani — kassir chegirmani qo'llaganda oshadi
    usage_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        # Bitta biznesda bir xil kategoriya ikki marta bo'lmasin
        constraints = [
            models.UniqueConstraint(fields=["business", "category"], name="uniq_business_discount_category")
        ]

    def __str__(self):
        return f"{self.business.name} · {self.category} {self.percent}%"


class DiscountChangeRequest(models.Model):
    """Biznes egasi chegirma o'zgarishini so'raydi -> Admin tasdiqlaydi.

    Uch xil o'zgarish (`action`):
      * `percent` — shartnomadagi asosiy foizni o'zgartirish (eski oqim);
      * `create`  — yangi chegirma KARTASINI qo'shish (Chegirmalar sahifasi);
      * `update`  — mavjud chegirma kartasini tahrirlash.

    Karta so'rovlarida taklif qilingan qiymatlar `category / new_percent /
    description / new_min_purchase / new_is_active` maydonlarida saqlanadi va
    admin tasdiqlagach `Discount` modeliga qo'llanadi. Shu vaqtgacha biznes
    egasi panelida karta KO'RINMAYDI — to'g'ridan-to'g'ri saqlanmaydi.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Ko'rib chiqilmoqda"
        APPROVED = "approved", "Tasdiqlangan"
        REJECTED = "rejected", "Rad etilgan"

    class Action(models.TextChoices):
        PERCENT = "percent", "Asosiy foizni o'zgartirish"
        CREATE = "create", "Yangi chegirma qo'shish"
        UPDATE = "update", "Chegirmani tahrirlash"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="discount_requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    action = models.CharField(max_length=12, choices=Action.choices, default=Action.PERCENT)
    # `update` uchun tahrirlanayotgan karta (create'da bo'sh)
    discount = models.ForeignKey(
        Discount,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="change_requests",
    )
    # Karta so'rovlari uchun taklif qilingan qiymatlar
    category = models.CharField(max_length=32, blank=True)
    description = models.CharField(max_length=255, blank=True)
    new_min_purchase = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    new_is_active = models.BooleanField(default=True)

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
        if self.action == self.Action.PERCENT:
            return f"{self.business.name}: {self.old_percent}% -> {self.new_percent}%"
        return f"{self.business.name}: {self.get_action_display()} · {self.category} {self.new_percent}%"


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
