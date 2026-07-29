from django.db import models


class Status(models.TextChoices):
    PREMIUM = "Premium", "Premium"
    NEW = "Yangi", "Yangi"
    OVERDUE = "Muddati o'tgan", "Muddati o'tgan"
    TRIAL = "Free Trial", "Free Trial"


class ActivityStatus(models.TextChoices):
    ACTIVE = "Faol", "Faol"
    INACTIVE = "Nofaol", "Nofaol"
    NEW = "Yangi", "Yangi"
    EXPIRED = "O'tgan", "O'tgan"


class ChurnReason(models.TextChoices):
    PAYMENT_OVERDUE = "To'lov muddati o'tib ketgan", "To'lov muddati o'tib ketgan"
    TOO_EXPENSIVE = "Narxi qimmat", "Narxi qimmat"
    OTHER_APP = "Boshqa ilova ishlatmoqda", "Boshqa ilova ishlatmoqda"
    OTHER = "Boshqa sabab", "Boshqa sabab"


UZ_REGIONS = [
    "Toshkent shahri",
    "Toshkent viloyati",
    "Samarqand",
    "Buxoro",
    "Andijon",
    "Farg'ona",
    "Namangan",
    "Qashqadaryo",
    "Surxondaryo",
    "Xorazm",
    "Navoiy",
    "Jizzax",
    "Sirdaryo",
    "Qoraqalpog'iston",
]

TASHKENT_DISTRICTS = [
    "Chilonzor tumani",
    "Yunusobod tumani",
    "Mirzo Ulug'bek tumani",
    "Yakkasaroy tumani",
    "Shayxontohur tumani",
    "Olmazor tumani",
    "Sergeli tumani",
    "Bektemir tumani",
]


class Member(models.Model):
    """A registered customer of the Savin mobile app ('Foydalanuvchi')."""

    member_code = models.CharField(max_length=16, unique=True)  # public ID, e.g. 123456789
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32)
    city = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    activity_status = models.CharField(
        max_length=20, choices=ActivityStatus.choices, default=ActivityStatus.ACTIVE
    )
    joined_at = models.DateField()

    # Savings accumulated through discounts ("Jamg'arma" / "Jami tejagan")
    savings_total = models.DecimalField(max_digits=12, decimal_places=0, default=0)

    # Subscription ("Obuna holati")
    membership_start = models.DateField(null=True, blank=True)
    membership_end = models.DateField(null=True, blank=True)
    months_subscribed = models.PositiveIntegerField(default=0)

    # Personal info
    device = models.CharField(max_length=64, blank=True)  # e.g. "iPhone 14 · iOS 17.2"
    push_enabled = models.BooleanField(default=True)

    # Referral program ("Referal holati")
    referral_code = models.CharField(max_length=16, blank=True)
    referral_invited = models.PositiveIntegerField(default=0)
    referral_target = models.PositiveIntegerField(default=3)

    # Blocking
    is_blocked = models.BooleanField(default=False)
    block_reason = models.CharField(max_length=150, blank=True)
    block_comment = models.TextField(blank=True)
    blocked_at = models.DateField(null=True, blank=True)

    # Last extension note ("Uzaytirildi: … · Sabab: … · +N oy")
    extended_at = models.DateField(null=True, blank=True)
    extend_reason = models.CharField(max_length=150, blank=True)
    extend_months = models.PositiveIntegerField(default=0)

    # Why the member churned (only set for churned members) — analytics
    churn_reason = models.CharField(max_length=64, choices=ChurnReason.choices, blank=True)

    class Meta:
        ordering = ["-joined_at", "-id"]

    def __str__(self):
        return self.name


class BusinessCategory(models.TextChoices):
    RESTORAN = "Restoran", "Restoran"
    KAFE = "Kafe", "Kafe"
    FITNESS = "Fitness", "Fitness"
    BARBER = "Barber", "Barber"
    SALON = "Salon", "Salon"
    AVTO = "Avto", "Avto"
    TIBBIYOT = "Tibbiyot", "Tibbiyot"
    SHIFOXONA = "Shifoxona", "Shifoxona"
    TALIM = "Ta'lim", "Ta'lim"
    TAXI = "Taxi", "Taxi"


class BusinessStatus(models.TextChoices):
    APPROVED = "Tasdiqlangan", "Tasdiqlangan"
    PENDING = "Kutilmoqda", "Kutilmoqda"
    REPEAT = "Takroriy", "Takroriy"
    REJECTED = "Rad etilgan", "Rad etilgan"
    BLOCKED = "Bloklangan", "Bloklangan"


class BusinessType(models.TextChoices):
    YATT = "YaTT", "YaTT (Yakka tartibli tadbirkor)"
    MCHJ = "MChJ", "MChJ"
    OK = "OK", "Oilaviy korxona"


class Business(models.Model):
    """A partner business registered on the Savin platform."""

    business_code = models.CharField(max_length=16, unique=True)  # public ID, e.g. 123456789
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=32, choices=BusinessCategory.choices)
    business_type = models.CharField(max_length=8, choices=BusinessType.choices, default=BusinessType.YATT)
    stir = models.CharField(max_length=16, blank=True)  # STIR / Soliq raqami
    owner = models.CharField(max_length=150)  # Mas'ul shaxs
    description = models.TextField(blank=True)

    # Contact
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    instagram = models.CharField(max_length=64, blank=True)
    telegram = models.CharField(max_length=64, blank=True)
    website = models.CharField(max_length=128, blank=True)

    # Location & working hours
    region = models.CharField(max_length=64, blank=True)  # Viloyat
    district = models.CharField(max_length=64, blank=True)  # Shahar / Tuman
    address = models.CharField(max_length=255, blank=True)  # To'liq manzil
    # Biznes egasi landing arizasida xaritada belgilagan lokatsiya
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    work_days = models.CharField(max_length=64, blank=True, default="Dushanba – Juma")
    work_hours = models.CharField(max_length=64, blank=True, default="09:00 - 18:00")

    # Discount
    discount_percent = models.PositiveIntegerField(default=0)
    min_purchase = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    discount_scope = models.CharField(max_length=64, default="Barcha mahsulotlar")

    # Panel credentials ("Kirish ma'lumotlari")
    login = models.CharField(max_length=64, blank=True)
    password = models.CharField(max_length=64, blank=True)

    # Uploaded contract document ("Hujjatlar")
    document_name = models.CharField(max_length=128, blank=True)
    document_size_kb = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=20, choices=BusinessStatus.choices, default=BusinessStatus.PENDING)
    reject_reason = models.TextField(blank=True)
    block_reason = models.TextField(blank=True)
    submitted_at = models.DateField()  # Topshirilgan sana
    registered_at = models.DateField(null=True, blank=True)  # Ro'yxatdan o'tgan sana

    class Meta:
        ordering = ["-submitted_at", "-id"]
        verbose_name_plural = "businesses"

    def __str__(self):
        return self.name


class TransactionStatus(models.TextChoices):
    SUCCESS = "Muvaffaqiyatli", "Muvaffaqiyatli"
    CANCELLED = "Bekor qilingan", "Bekor qilingan"


class BusinessTransaction(models.Model):
    """A QR discount transaction at a partner business (biznes 'To'lovlar tarixi')."""

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="transactions")
    member = models.ForeignKey(
        Member, on_delete=models.SET_NULL, null=True, blank=True, related_name="visits"
    )
    member_name = models.CharField(max_length=150)
    cashier = models.CharField(max_length=64, blank=True)  # Kassir
    original_amount = models.DecimalField(max_digits=12, decimal_places=0)
    final_amount = models.DecimalField(max_digits=12, decimal_places=0)
    status = models.CharField(
        max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.SUCCESS
    )
    created_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member_name} @ {self.business.name}"


class ApplicationStatus(models.TextChoices):
    NEW = "Yangi", "Yangi"
    REVIEWING = "Ko'rib chiqilmoqda", "Ko'rib chiqilmoqda"
    CONTACTED = "Bog'lanildi", "Bog'lanildi"
    APPROVED = "Tasdiqlangan", "Tasdiqlangan"
    CREATED = "Biznes yaratildi", "Biznes yaratildi"
    REJECTED = "Rad etildi", "Rad etildi"


class BusinessApplication(models.Model):
    """A partnership request submitted from the landing website ('Arizalar')."""

    business_name = models.CharField(max_length=150)
    category = models.CharField(max_length=32, choices=BusinessCategory.choices)
    phone = models.CharField(max_length=32)
    region = models.CharField(max_length=64)
    discount_percent = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=32, choices=ApplicationStatus.choices, default=ApplicationStatus.NEW)
    created_at = models.DateTimeField()

    # Asosiy backend'dagi (savin_django) ariza ID'si — tasdiqlash/rad etish
    # natijasini o'sha tomonga qaytarish (reverse bridge) uchun.
    source_id = models.CharField(max_length=64, blank=True)

    # Landing arizasining to'liq tafsiloti (detail oynasida ko'rsatiladi)
    responsible_name = models.CharField(max_length=150, blank=True)
    business_type = models.CharField(max_length=16, blank=True)
    description = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    instagram = models.CharField(max_length=64, blank=True)
    telegram = models.CharField(max_length=64, blank=True)
    website = models.CharField(max_length=128, blank=True)
    district = models.CharField(max_length=64, blank=True)
    address = models.CharField(max_length=255, blank=True)
    # Biznes egasi xaritada belgilagan lokatsiya
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    work_days = models.CharField(max_length=64, blank=True)
    work_hours = models.CharField(max_length=64, blank=True)
    min_purchase = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    discount_scope = models.CharField(max_length=64, blank=True)
    # Biznes egasi landing'da tanlagan panel kirish ma'lumotlari
    login = models.CharField(max_length=64, blank=True)
    password = models.CharField(max_length=64, blank=True)
    # Rad etish sababi (admin kiritadi)
    reject_reason = models.TextField(blank=True)
    # Tasdiqlanganda yaratilgan biznes
    created_business = models.ForeignKey(
        Business, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="from_applications",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.business_name


class PaymentMethod(models.TextChoices):
    CLICK = "Click", "Click"
    PAYME = "Payme", "Payme"
    HUMO = "Humo/Uzcard", "Humo/Uzcard"


class PaymentStatus(models.TextChoices):
    SUCCESS = "Muvaffaqiyatli", "Muvaffaqiyatli"
    PENDING = "Kutilmoqda", "Kutilmoqda"
    REFUNDED = "Qaytarilgan", "Qaytarilgan"


class Payment(models.Model):
    """A subscription payment made in the Savin app ('To'lovlar')."""

    txn_id = models.CharField(max_length=32, unique=True)
    member = models.ForeignKey(
        Member, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments"
    )
    user_display_name = models.CharField(max_length=150)
    months = models.PositiveIntegerField(default=1)  # subscription length paid for
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    method = models.CharField(max_length=16, choices=PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices)
    psp_ref = models.CharField(max_length=32, blank=True)  # To'lov tizimi ref, e.g. CLK-98723645
    period_start = models.DateField(null=True, blank=True)  # Obuna davri
    period_end = models.DateField(null=True, blank=True)
    refund_reason = models.CharField(max_length=150, blank=True)
    refund_comment = models.TextField(blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.txn_id


class AudienceType(models.TextChoices):
    ALL = "all", "Barcha foydalanuvchilar"
    PREMIUM = "premium", "Premium a'zolar"
    CATEGORY = "category", "Kategoriya bo'yicha"
    INDIVIDUAL = "individual", "Alohida odam"


class Notification(models.Model):
    """A push notification composed in the admin panel ('Bildirishnomalar')."""

    title = models.CharField(max_length=150)
    body = models.TextField()
    audience_type = models.CharField(max_length=16, choices=AudienceType.choices, default=AudienceType.ALL)
    category = models.CharField(max_length=32, choices=BusinessCategory.choices, blank=True)
    member = models.ForeignKey(
        Member, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications"
    )
    language = models.CharField(max_length=8, default="uz")  # uz / ru / en
    send_time = models.CharField(max_length=16, default="Hozir")  # Hozir / 19:00 / 20:00 / 21:00
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered = models.PositiveIntegerField(default=0)
    opened = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return self.title


class DailyActivity(models.Model):
    """Daily app usage counters powering the activity charts ('Kunlik va oylik faollik')."""

    date = models.DateField(unique=True)
    daily_active = models.PositiveIntegerField(default=0)  # a'zolar shu kuni ilovaga kirgan
    qr_scans = models.PositiveIntegerField(default=0)
    peak_hour = models.PositiveIntegerField(default=18)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return self.date.isoformat()


class PlatformStat(models.Model):
    """Singleton funnel counters ('Yuklab olishdan to'lashgacha')."""

    downloads = models.PositiveIntegerField(default=0)  # Ilovani yuklab oldi
    registrations = models.PositiveIntegerField(default=0)  # Ro'yxatdan o'tdi
    payment_page_opens = models.PositiveIntegerField(default=0)  # To'lov sahifasini ochdi

    def __str__(self):
        return "Platform stats"


class AdminAlertKind(models.TextChoices):
    BUSINESS_APPLICATION = "business_application", "Biznes arizasi"
    MEMBER_JOINED = "member_joined", "Yangi a'zo"
    PUSH_SENT = "push_sent", "Push yuborildi"
    BUSINESS_APPROVED = "business_approved", "Biznes tasdiqlandi"
    # Biznes panelidan kelgan so'rovlar (masalan, chegirma foizini o'zgartirish)
    BUSINESS_REQUEST = "business_request", "Biznes so'rovi"
    # Mijoz (mobil ilova foydalanuvchisi) yuborgan referal mukofot so'rovi
    REFERRAL_REQUEST = "referral_request", "Referal so'rovi"


class ReferralRequestStatus(models.TextChoices):
    PENDING = "Kutilmoqda", "Kutilmoqda"
    APPROVED = "Tasdiqlangan", "Tasdiqlangan"
    REJECTED = "Rad etilgan", "Rad etilgan"


class ReferralRequest(models.Model):
    """Mijoz 3 ta do'st taklif qilib yuborgan mukofot so'rovi.

    Asosiy backenddan (savin_django) bridge orqali keladi. Admin tasdiqlaydi
    (mijoz a'zoligi +1 oy uzayadi) yoki sabab bilan rad etadi — natija asosiy
    backendga qaytariladi va mijozga bildirishnoma boradi.
    """

    source_id = models.CharField(max_length=64, unique=True)  # savin_django ReferralRequest id
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, null=True, blank=True, related_name="referral_requests"
    )
    member_name = models.CharField(max_length=150)
    member_phone = models.CharField(max_length=32, blank=True)
    invited_count = models.PositiveIntegerField(default=3)
    status = models.CharField(
        max_length=20,
        choices=ReferralRequestStatus.choices,
        default=ReferralRequestStatus.PENDING,
    )
    reject_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Referral: {self.member_name} (+{self.invited_count})"


class BusinessRequestStatus(models.TextChoices):
    PENDING = "Kutilmoqda", "Kutilmoqda"
    APPROVED = "Tasdiqlangan", "Tasdiqlangan"
    REJECTED = "Rad etilgan", "Rad etilgan"


class BusinessRequest(models.Model):
    """Biznes egasi biznes panelidan yuborgan so'rov (masalan chegirma
    foizini o'zgartirish). Asosiy backend'dan bridge orqali keladi; admin
    biznes detail sahifasining "So'rovlar" bo'limida tasdiqlaydi/rad etadi —
    natija asosiy backendga qaytariladi (biznes egasiga bildirishnoma boradi).
    """

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="requests"
    )
    # Asosiy backend'dagi DiscountChangeRequest ID'si (bridge uchun)
    source_id = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=32, default="discount_request")
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=300, blank=True)
    old_percent = models.PositiveIntegerField(default=0)
    new_percent = models.PositiveIntegerField(default=0)
    reason = models.TextField(blank=True)  # biznes egasining sababi
    status = models.CharField(
        max_length=20,
        choices=BusinessRequestStatus.choices,
        default=BusinessRequestStatus.PENDING,
    )
    reject_reason = models.TextField(blank=True)  # admin rad etish sababi
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business.name}: {self.old_percent}% -> {self.new_percent}%"


class AdminAlert(models.Model):
    """Internal admin-panel notifications (bell icon)."""

    kind = models.CharField(
        max_length=32, choices=AdminAlertKind.choices, default=AdminAlertKind.BUSINESS_APPLICATION
    )
    title = models.CharField(max_length=150)
    body = models.CharField(max_length=255, blank=True)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, null=True, blank=True, related_name="alerts"
    )
    # Yangi a'zo haqidagi bildirishnoma bosilganda o'sha foydalanuvchi ochiladi
    member = models.ForeignKey(
        "Member", on_delete=models.CASCADE, null=True, blank=True, related_name="alerts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
