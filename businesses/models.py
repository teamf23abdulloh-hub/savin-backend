import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

uzbek_phone_validator = RegexValidator(
    regex=r"^\+998\d{9}$",
    message="Telefon raqami +998XXXXXXXXX formatida bo'lishi kerak (masalan: +998900000000).",
)


class Category(models.Model):
    """Biznes turi/kategoriyasi (Tanlang / YaTT / MCHJ kabi biznes turi ham shu yerda bo'lishi mumkin)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class BusinessType(models.TextChoices):
    YATT = "yatt", "YaTT"
    MCHJ = "mchj", "MCHJ"


class WorkDay(models.TextChoices):
    MON_FRI = "mon_fri", "Dushanba - Juma"
    MON_SAT = "mon_sat", "Dushanba - Shanba"
    EVERYDAY = "everyday", "Har kuni"


class Region(models.TextChoices):
    """Wizard Step 3 — Viloyat * (dropdown). O'zbekiston hududlari."""

    TASHKENT_CITY = "tashkent_city", "Toshkent shahar"
    TASHKENT_REGION = "tashkent_region", "Toshkent viloyati"
    ANDIJAN = "andijan", "Andijon"
    BUKHARA = "bukhara", "Buxoro"
    FERGANA = "fergana", "Farg'ona"
    JIZZAKH = "jizzakh", "Jizzax"
    KASHKADARYA = "kashkadarya", "Qashqadaryo"
    NAVOIY = "navoiy", "Navoiy"
    NAMANGAN = "namangan", "Namangan"
    SAMARKAND = "samarkand", "Samarqand"
    SURKHANDARYA = "surkhandarya", "Surxondaryo"
    SIRDARYO = "sirdaryo", "Sirdaryo"
    KHOREZM = "khorezm", "Xorazm"
    KARAKALPAKSTAN = "karakalpakstan", "Qoraqalpog'iston"


class Application(models.Model):
    """
    Ariza qoldirish - 4 qadamli wizard:
    1) Biznes  2) Kontakt  3) Joylashuv  4) Chegirma
    Admin panel: Arizalar ro'yxati -> Yangi ariza ko'rish -> Tasdiqlash / Rad etish
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        PENDING = "pending", "Ko'rib chiqilmoqda"
        APPROVED = "approved", "Tasdiqlangan"
        REJECTED = "rejected", "Rad etilgan"

    class DiscountType(models.TextChoices):
        FIXED = "fixed", "Barcha mahsulotlar"
        MIN_PURCHASE = "min_purchase", "Minimal xarid summasi"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
        null=True,
        blank=True,
    )
    # --- Step 1: Biznes ---
    business_name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="applications"
    )
    business_type = models.CharField(max_length=10, choices=BusinessType.choices)
    responsible_full_name = models.CharField(max_length=255)
    short_description = models.TextField(blank=True)

    # --- Step 2: Kontakt ---
    phone_number = models.CharField(max_length=13, validators=[uzbek_phone_validator])
    email = models.EmailField(blank=True)
    instagram = models.CharField(max_length=150, blank=True)
    telegram = models.CharField(max_length=150, blank=True)
    website = models.CharField(
        max_length=255, blank=True
    )  # protokolsiz ham qabul qilinadi (www.biznes.uz)

    # --- Step 3: Joylashuv ---
    region = models.CharField(max_length=30, choices=Region.choices)
    city_district = models.CharField(max_length=120)
    full_address = models.CharField(max_length=500)
    work_days = models.CharField(
        max_length=20, choices=WorkDay.choices, default=WorkDay.EVERYDAY
    )
    work_hours_from = models.TimeField(blank=True, null=True)
    work_hours_to = models.TimeField(blank=True, null=True)
    # Aniq lokatsiya (lat/long) ariza beruvchi tomonidan emas, balki
    # operator/admin tomonidan tasdiqlash bosqichida belgilanadi (rasmdagi eslatmaga mos).
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )

    # --- Step 4: Chegirma ---
    discount_percent = models.PositiveSmallIntegerField(
        default=10,
        validators=[
            MinValueValidator(5, message="Chegirma foizi kamida 5%% bo'lishi kerak."),
            MaxValueValidator(
                100, message="Chegirma foizi 100%% dan oshmasligi kerak."
            ),
        ],
    )
    min_purchase_amount = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    discount_type = models.CharField(
        max_length=20, choices=DiscountType.choices, default=DiscountType.FIXED
    )

    # --- Step 4: Biznes panel kirish ma'lumotlari ---
    # Biznes egasi kelajakdagi biznes paneli uchun o'zi tanlagan login (email
    # ko'rinishida, @savin.uz bilan) va parol. Ariza tasdiqlanganda shu login/
    # parol bilan biznes egasi hisobi (User) yaratiladi. Parol admin panelда
    # ko'rsatilishi uchun ochiq saqlanadi (User yaratilganda esa hash bo'ladi).
    panel_login = models.EmailField(blank=True)
    panel_password = models.CharField(max_length=128, blank=True)

    # --- Wizard progress / status ---
    current_step = models.PositiveSmallIntegerField(default=1)  # 1..4
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    rejection_reason = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_applications",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business_name} - {self.status}"


class Business(models.Model):
    """Tasdiqlangan arizadan yaratiladigan faol biznes (listing)."""

    class PartnershipStatus(models.TextChoices):
        ACTIVE = "active", "Faol hamkorlik"
        PAUSED = "paused", "To'xtatilgan"
        STOPPED = "stopped", "Bekor qilingan"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_businesses",
    )
    application = models.OneToOneField(
        Application,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="business",
    )

    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="businesses"
    )
    business_type = models.CharField(max_length=10, choices=BusinessType.choices)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="business_logos/", blank=True, null=True)

    phone_number = models.CharField(max_length=13, validators=[uzbek_phone_validator])
    email = models.EmailField(blank=True)
    instagram = models.CharField(max_length=150, blank=True)
    telegram = models.CharField(max_length=150, blank=True)
    website = models.CharField(max_length=255, blank=True)

    region = models.CharField(max_length=30, choices=Region.choices)
    city_district = models.CharField(max_length=120)
    full_address = models.CharField(max_length=500)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )

    partnership_status = models.CharField(
        max_length=20,
        choices=PartnershipStatus.choices,
        default=PartnershipStatus.ACTIVE,
    )
    contract_signed = models.BooleanField(default=False)
    qr_code = models.ImageField(upload_to="qr_codes/", blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Businesses"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Service(models.Model):
    """Biznes xizmatlari katalogi (narxi bilan).

    Kassir tranzaksiya yaratishda shu ro'yxatdan xizmat tanlaydi;
    biznes egasi ro'yxatni o'zi boshqaradi.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="services"
    )
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("business", "name")

    def __str__(self):
        return f"{self.name} ({self.business.name})"


class Cashier(models.Model):
    """Biznes egasi qo'shgan kassirlar ro'yxati."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="cashiers"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cashier_profile",
    )
    full_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} @ {self.business.name}"
