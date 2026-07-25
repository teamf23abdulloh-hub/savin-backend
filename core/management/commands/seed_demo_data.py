import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import AccountSettings, NotificationPreference
from core.models import (
    ActivityStatus,
    AdminAlert,
    AdminAlertKind,
    ApplicationStatus,
    AudienceType,
    Business,
    BusinessApplication,
    BusinessCategory,
    BusinessStatus,
    BusinessTransaction,
    BusinessType,
    ChurnReason,
    DailyActivity,
    Member,
    Notification,
    Payment,
    PaymentMethod,
    PaymentStatus,
    PlatformStat,
    Status,
    TransactionStatus,
    TASHKENT_DISTRICTS,
    UZ_REGIONS,
)

FIRST_NAMES = [
    "Aziz", "Dilnoza", "Jasur", "Malika", "Sardor", "Zarina", "Bekzod", "Nigora",
    "Otabek", "Shahnoza", "Farrux", "Gulnora", "Islom", "Madina", "Rustam", "Yulduz",
    "Davron", "Kamola", "Anvar", "Sevara", "Bobur", "Nodira", "Temur", "Laylo",
    "Ulug'bek", "Feruza", "Shohruh", "Dildora", "Akmal", "Munisa",
]
LAST_NAMES = [
    "Karimov", "Yusupova", "Rahimov", "Hasanova", "Toshmatov", "Ergashev", "Nazarova",
    "Xolmatov", "Saidova", "Umarov", "Aliyeva", "Turg'unov", "Rahimova", "Qodirov",
    "Yoqubova", "Mirzayev", "Islomova", "Sultonov", "Karimova", "Abdullayev",
]

CASHIERS = ["Dilnoza.X", "Aziza.M", "Jasur.T", "Kamola.R", "Sardor.B", "Feruza.N"]

DEVICES = [
    "iPhone 14 · iOS 17.2", "iPhone 13 · iOS 16.6", "iPhone 15 Pro · iOS 17.4",
    "Samsung S23 · Android 14", "Redmi Note 12 · Android 13", "Pixel 7 · Android 14",
    "Samsung A54 · Android 14", "iPhone 12 · iOS 16.2",
]

CITIES = [
    "Toshkent shahri", "Toshkent shahri", "Toshkent shahri", "Toshkent shahri",
    "Samarqand", "Buxoro", "Andijon", "Farg'ona", "Namangan", "Xorazm",
]

# Category -> (name templates, typical bill range)
BUSINESS_NAME_POOL = {
    BusinessCategory.RESTORAN: ["Bahor Restorani", "Osiyo Taomlari", "Milliy Taomlar Uyi", "Sultan Restoran", "Afsona Restoran", "Riviera Restoran", "Buxoro Oshxonasi", "Samarqand Darvoza"],
    BusinessCategory.KAFE: ["Green Coffee", "Coffee Mood", "Bon! Kafe", "Safia", "Brew Lab", "Kofe Uyi", "Choyxona No1", "Sweet Corner"],
    BusinessCategory.FITNESS: ["FitLife Gym", "GreenFit Gym", "PowerHouse Gym", "Olimp Fitness", "Energy Fitness", "Atletika Club", "FitZone", "Yoga Space"],
    BusinessCategory.BARBER: ["Star Barber", "Fresh Cut Barber", "King's Barber", "BarberPro", "Usta Sartarosh", "Elite Barber", "Golden Razor", "Barber Bros"],
    BusinessCategory.SALON: ["Elegance Salon", "Beauty Lab", "Yasmin Go'zallik Saloni", "Glamour Studio", "Malika Beauty", "Nilufar Salon", "Aura Beauty", "Zebo Salon"],
    BusinessCategory.AVTO: ["AutoPro Servis", "Motor Servis", "AvtoRitm", "Drive Master", "TurboAvto", "AvtoDoktor", "Shina Market", "AvtoLux"],
    BusinessCategory.TIBBIYOT: ["Hayot Dorixona", "Shifo Dorixonasi", "MedPlus Apteka", "Salomatlik Dorixona", "Farmatsiya 24", "Dori-Darmon"],
    BusinessCategory.SHIFOXONA: ["SmartMed Klinika", "Salomatlik Klinikasi", "MedLine Klinika", "Doktor Plus", "Vita Klinika", "Nur Shifoxona"],
    BusinessCategory.TALIM: ["Tafakkur Ta'lim Markazi", "Cambridge School", "IT Academy", "Zakovat O'quv Markazi", "English Life", "Registon Edu"],
    BusinessCategory.TAXI: ["City Taxi", "Express Taxi", "Lider Taxi", "Salom Taxi"],
}

BILL_RANGE = {
    BusinessCategory.RESTORAN: (80_000, 400_000),
    BusinessCategory.KAFE: (30_000, 120_000),
    BusinessCategory.FITNESS: (200_000, 500_000),
    BusinessCategory.BARBER: (40_000, 120_000),
    BusinessCategory.SALON: (60_000, 300_000),
    BusinessCategory.AVTO: (100_000, 800_000),
    BusinessCategory.TIBBIYOT: (30_000, 200_000),
    BusinessCategory.SHIFOXONA: (100_000, 600_000),
    BusinessCategory.TALIM: (300_000, 900_000),
    BusinessCategory.TAXI: (15_000, 60_000),
}

PLAN_PRICES = {1: 20_000, 3: 60_000, 6: 120_000}


class Command(BaseCommand):
    help = "Seed the database with realistic demo data matching the Savin Admin design."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete existing data first.")

    def handle(self, *args, **options):
        if options["flush"]:
            for model in (
                BusinessTransaction, Payment, Notification, AdminAlert,
                BusinessApplication, DailyActivity, PlatformStat, Business, Member,
            ):
                model.objects.all().delete()
            self.stdout.write("Eski ma'lumotlar o'chirildi.")

        random.seed(42)
        self._create_admin_users()
        members = self._create_members()
        businesses = self._create_businesses()
        self._create_payments(members)
        self._create_transactions(businesses, members)
        self._create_applications()
        self._create_daily_activity()
        self._create_platform_stats()
        self._create_notifications(members)
        self._create_alerts()

        self.stdout.write(self.style.SUCCESS("Demo ma'lumotlar muvaffaqiyatli yaratildi."))

    # ------------------------------------------------------------------
    def _create_admin_users(self):
        User = get_user_model()
        for username, password, first, last in (
            ("admin", "admin12345", "Alisher", "Yusupov"),
            ("adminpanel123", "Afterglow", "Savin", "Admin"),
        ):
            if User.objects.filter(username=username).exists():
                continue
            user = User.objects.create_superuser(
                username=username,
                email=f"{username}@savin.uz",
                password=password,
                first_name=first,
                last_name=last,
                phone="+998932425999",
            )
            NotificationPreference.objects.create(user=user)
            AccountSettings.objects.create(user=user)
            self.stdout.write(f"Admin yaratildi: {username} / {password}")

    # ------------------------------------------------------------------
    def _random_name(self):
        return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

    def _random_phone(self):
        return f"+998 {random.randint(88, 99)} {random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}"

    def _member_code(self, used):
        while True:
            code = str(random.randint(100_000_000, 199_999_999))
            if code not in used:
                used.add(code)
                return code

    def _create_members(self):
        today = timezone.now().date()
        used_codes = set()
        members = []

        def make(name, status, activity, joined_days_ago, savings, months, end_in_days, **extra):
            joined = today - timedelta(days=joined_days_ago)
            start = extra.pop("start", None) or max(joined, today - timedelta(days=random.randint(10, 80)))
            end = today + timedelta(days=end_in_days) if end_in_days is not None else None
            first = name.split()[0].upper()[:6]
            return Member(
                member_code=extra.pop("member_code", None) or self._member_code(used_codes),
                name=name,
                phone=extra.pop("phone", None) or self._random_phone(),
                city=extra.pop("city", None) or random.choice(CITIES),
                status=status,
                activity_status=activity,
                joined_at=joined,
                savings_total=savings,
                membership_start=start if end else None,
                membership_end=end,
                months_subscribed=months,
                device=random.choice(DEVICES),
                push_enabled=random.random() > 0.15,
                referral_code=f"{first}-{random.randint(1000, 9999)}",
                referral_invited=extra.pop("referral_invited", random.randint(0, 3)),
                referral_target=3,
                **extra,
            )

        # --- Named members from the design ------------------------------
        members.append(
            make(
                "Aziz Karimov", Status.PREMIUM, ActivityStatus.ACTIVE,
                joined_days_ago=185, savings=247_500, months=4, end_in_days=17,
                member_code="123456789", phone="+998 90 123 45 67", city="Toshkent shahri",
                start=today - timedelta(days=13), referral_invited=2,
            )
        )
        members.append(
            make(
                "Malika Yusupova", Status.OVERDUE, ActivityStatus.INACTIVE,
                joined_days_ago=186, savings=183_200, months=3, end_in_days=None,
                phone="+998 90 123 45 67", churn_reason=ChurnReason.PAYMENT_OVERDUE,
            )
        )
        members.append(
            make(
                "Jasur Rahimov", Status.NEW, ActivityStatus.NEW,
                joined_days_ago=6, savings=94_800, months=0, end_in_days=None,
            )
        )
        members.append(
            make(
                "Nodira Hasanova", Status.TRIAL, ActivityStatus.EXPIRED,
                joined_days_ago=98, savings=312_100, months=0, end_in_days=None,
            )
        )
        members.append(
            make(
                "Bobur Toshmatov", Status.TRIAL, ActivityStatus.ACTIVE,
                joined_days_ago=9, savings=12_500, months=0, end_in_days=5,
            )
        )

        # --- Bulk members -------------------------------------------------
        # Target: ~5,247 total / ~4,108 premium / ~632 overdue / ~507 new this month
        specs = []
        specs += [(Status.PREMIUM, ActivityStatus.ACTIVE)] * 4105
        specs += [(Status.OVERDUE, ActivityStatus.INACTIVE)] * 630
        specs += [(Status.TRIAL, ActivityStatus.ACTIVE)] * 210
        specs += [(Status.NEW, ActivityStatus.NEW)] * 297
        random.shuffle(specs)

        month_first = today.replace(day=1)
        days_in_month = (today - month_first).days

        churn_pool = []
        for i, (st, act) in enumerate(specs):
            if st == Status.NEW or (i % 10 == 0 and st != Status.OVERDUE):
                joined_days_ago = random.randint(0, max(days_in_month, 1))
            else:
                joined_days_ago = random.randint(days_in_month + 1, 420)

            months = 0
            end_in = None
            savings = random.randint(5_000, 180_000)
            if st == Status.PREMIUM:
                months = random.choice([1, 1, 2, 3, 4, 6, 8, 12])
                end_in = random.randint(1, 90)
                savings = random.randint(40_000, 480_000)
            elif st == Status.TRIAL:
                end_in = random.randint(1, 7)
            elif st == Status.OVERDUE:
                savings = random.randint(20_000, 260_000)

            m = make(self._random_name(), st, act, joined_days_ago, savings, months, end_in)
            if st == Status.OVERDUE:
                churn_pool.append(m)
            members.append(m)

        # Churn reasons — 3.2% of all members (design: 68/18/9/5 split)
        churn_n = round(len(members) * 0.032)
        random.shuffle(churn_pool)
        splits = [
            (ChurnReason.PAYMENT_OVERDUE, round(churn_n * 0.68)),
            (ChurnReason.TOO_EXPENSIVE, round(churn_n * 0.18)),
            (ChurnReason.OTHER_APP, round(churn_n * 0.09)),
            (ChurnReason.OTHER, churn_n - round(churn_n * 0.68) - round(churn_n * 0.18) - round(churn_n * 0.09)),
        ]
        idx = 0
        for reason, count in splits:
            for _ in range(count):
                if idx >= len(churn_pool):
                    break
                churn_pool[idx].churn_reason = reason
                idx += 1

        # A handful of blocked members
        for m in random.sample(members[5:], 14):
            m.is_blocked = True
            m.block_reason = random.choice(
                ["Shubhali faollik", "To'lov muammosi", "Foydalanuvchi so'rovi"]
            )
            m.blocked_at = today - timedelta(days=random.randint(1, 60))
            m.activity_status = ActivityStatus.INACTIVE

        Member.objects.bulk_create(members, batch_size=500)
        self.stdout.write(f"{len(members)} a'zo yaratildi.")
        return list(Member.objects.all())

    # ------------------------------------------------------------------
    def _create_businesses(self):
        today = timezone.now().date()
        used_codes = set()
        businesses = []

        def code():
            while True:
                c = str(random.randint(200_000_000, 299_999_999))
                if c not in used_codes:
                    used_codes.add(c)
                    return c

        def slugify(name):
            return (
                name.lower()
                .replace("'", "")
                .replace("’", "")
                .replace(" ", "")
                .replace("!", "")[:14]
            )

        def make(name, category, status, discount, days_ago, region=None, district=None, **extra):
            submitted = today - timedelta(days=days_ago)
            registered = submitted if status in (BusinessStatus.APPROVED, BusinessStatus.BLOCKED) else None
            slug = slugify(name)
            region = region or extra.pop("region", None) or random.choice(CITIES)
            district = district or extra.pop("district", None) or (
                random.choice(TASHKENT_DISTRICTS) if region == "Toshkent shahri" else f"{region} markazi"
            )
            kwargs = dict(
                business_code=code(),
                name=name,
                category=category,
                business_type=random.choice(list(BusinessType.values)),
                stir=str(random.randint(300_000_000, 309_999_999)),
                owner=self._random_name(),
                description=f"{name} — {category.lower()} yo'nalishidagi hamkor biznes.",
                phone=self._random_phone(),
                email=f"info@{slug}.uz",
                instagram=f"@{slug}",
                telegram=f"t.me/{slug}",
                website=f"www.{slug}.uz",
                region=region,
                district=district,
                address=f"{random.choice(['Bunyodkor', 'Amir Temur', 'Mustaqillik', 'Navoiy', 'Bobur'])} ko'chasi, {random.randint(1, 120)}-uy",
                work_days=random.choice(["Dushanba – Juma", "Dushanba – Shanba", "Har kuni"]),
                work_hours=random.choice(["09:00 - 18:00", "09:00 - 22:00", "10:00 - 20:00", "08:00 - 23:00"]),
                discount_percent=discount,
                min_purchase=random.choice([0, 20_000, 30_000, 50_000, 100_000]),
                discount_scope="Barcha mahsulotlar",
                login=f"{slug.capitalize()}123",
                password=f"{random.randint(10000, 99999)}qwert",
                document_name=f"{name}.pdf",
                document_size_kb=random.randint(180, 900),
                status=status,
                reject_reason="Hujjatlar to'liq emas, qayta yuborish talab etiladi."
                if status == BusinessStatus.REJECTED
                else "",
                submitted_at=submitted,
                registered_at=registered,
            )
            kwargs.update(extra)
            return Business(**kwargs)

        # --- Named businesses from the design -----------------------------
        named = [
            ("Baraka Restoran", BusinessCategory.RESTORAN, BusinessStatus.APPROVED, 20, 98,
             dict(owner="Bahodir Toshmatov", phone="+998 90 123 45 67", region="Toshkent shahri",
                  district="Chilonzor tumani", address="Bunyodkor ko'chasi, 12-uy, 1-qavat",
                  business_type=BusinessType.YATT, stir="302345678", email="info@baraka.uz",
                  instagram="@baraka_restoran", login="Baraka123", password="123455qwert",
                  work_hours="09:00 - 22:00", work_days="Dushanba – Shanba",
                  description="Chet eldan ming xil texnikalarni olib kelamiz",
                  document_name="Baraka Restoran.pdf", document_size_kb=520, min_purchase=50_000)),
            ("FitLife Gym", BusinessCategory.FITNESS, BusinessStatus.PENDING, 5, 101,
             dict(region="Toshkent shahri", district="Yunusobod tumani")),
            ("Star Barber", BusinessCategory.BARBER, BusinessStatus.APPROVED, 5, 103, dict(region="Samarqand")),
            ("Hayot Dorixona", BusinessCategory.TIBBIYOT, BusinessStatus.REPEAT, 10, 104, dict(region="Namangan")),
            ("Elegance Salon", BusinessCategory.SALON, BusinessStatus.APPROVED, 15, 105,
             dict(region="Toshkent shahri", district="Mirzo Ulug'bek tumani")),
            ("Pizza House", BusinessCategory.RESTORAN, BusinessStatus.PENDING, 10, 105,
             dict(region="Toshkent shahri")),
            ("AutoPro Servis", BusinessCategory.AVTO, BusinessStatus.PENDING, 10, 105, {}),
            ("Safia", BusinessCategory.KAFE, BusinessStatus.REJECTED, 5, 105, {}),
            ("SmartMed Klinika", BusinessCategory.SHIFOXONA, BusinessStatus.PENDING, 2, 106, {}),
            ("Green Coffee", BusinessCategory.KAFE, BusinessStatus.APPROVED, 10, 106, {}),
        ]
        stir_override = None
        for name, cat, st, disc, days, extra in named:
            stir_val = extra.pop("stir", None)
            b = make(name, cat, st, disc, days, **extra)
            if stir_val:
                b.stir = stir_val
            businesses.append(b)

        # --- Bulk businesses ----------------------------------------------
        # Target ≈ design stats: 132 jami / 118 faol / 9 kutilayotgan / 5 bloklangan
        statuses = (
            [BusinessStatus.APPROVED] * 114
            + [BusinessStatus.PENDING] * 3
            + [BusinessStatus.REPEAT] * 1
            + [BusinessStatus.BLOCKED] * 5
            + [BusinessStatus.REJECTED] * 3
        )
        random.shuffle(statuses)
        used_names = {b.name for b in businesses}
        for st in statuses:
            cat = random.choice(list(BusinessCategory.values))
            pool = [n for n in BUSINESS_NAME_POOL[cat] if n not in used_names]
            if not pool:
                base = random.choice(BUSINESS_NAME_POOL[cat])
                name = f"{base} {random.choice(['Plus', 'Pro', 'City', 'Chilonzor', 'Yunusobod', 'Sergeli', '24/7'])}"
                if name in used_names:
                    name = f"{base} {random.randint(2, 99)}"
            else:
                name = random.choice(pool)
            used_names.add(name)
            discount = random.choice([1, 2, 3, 5, 5, 10, 10, 12, 15, 20, 25])
            b = make(name, cat, st, discount, random.randint(3, 300))
            if st == BusinessStatus.BLOCKED:
                b.block_reason = "Shartnoma shartlari buzilgan"
            businesses.append(b)

        Business.objects.bulk_create(businesses, batch_size=200)
        self.stdout.write(f"{len(businesses)} biznes yaratildi.")
        return list(Business.objects.all())

    # ------------------------------------------------------------------
    def _create_payments(self, members):
        now = timezone.now()
        payments = []
        counter = 10_000  # named TRX ids above stay below this range

        premium_members = [m for m in members if m.status == Status.PREMIUM]

        # --- Aziz Karimov's payment history (design: To'lovlar tarixi) ----
        aziz = next((m for m in members if m.member_code == "123456789"), None)
        if aziz:
            history = [
                ("TRX-2026-00247", 1, PaymentMethod.CLICK, PaymentStatus.SUCCESS, 94, "CLK-98723645"),
                ("TRX-2026-00198", 3, PaymentMethod.PAYME, PaymentStatus.SUCCESS, 125, "PYM-55201983"),
                ("TRX-2026-00143", 1, PaymentMethod.CLICK, PaymentStatus.SUCCESS, 155, "CLK-91180042"),
                ("TRX-2026-00089", 1, PaymentMethod.CLICK, PaymentStatus.REFUNDED, 185, "CLK-88410276"),
            ]
            for txn, months, method, st, days_ago, ref in history:
                created = now - timedelta(days=days_ago, hours=random.randint(1, 9))
                payments.append(
                    Payment(
                        txn_id=txn,
                        member=aziz,
                        user_display_name=aziz.name,
                        months=months,
                        amount=20_000,
                        method=method,
                        status=st,
                        psp_ref=ref,
                        period_start=created.date(),
                        period_end=created.date() + timedelta(days=30 * months),
                        refund_reason="Foydalanuvchi so'rovi" if st == PaymentStatus.REFUNDED else "",
                        refunded_at=created + timedelta(hours=5) if st == PaymentStatus.REFUNDED else None,
                        created_at=created,
                    )
                )

        # --- Bulk payments: ~4,800 over the last 8 months -------------------
        target = 4_800
        for i in range(target):
            member = random.choice(premium_members) if premium_members else random.choice(members)
            months = random.choices([1, 3, 6], weights=[0.72, 0.2, 0.08])[0]
            status_choice = random.choices(
                [PaymentStatus.SUCCESS, PaymentStatus.PENDING, PaymentStatus.REFUNDED],
                weights=[0.965, 0.02, 0.015],
            )[0]
            method = random.choices(
                list(PaymentMethod.values), weights=[0.5, 0.3, 0.2]
            )[0]
            created = now - timedelta(
                days=random.randint(0, 240), hours=random.randint(0, 23), minutes=random.randint(0, 59)
            )
            prefix = {"Click": "CLK", "Payme": "PYM", "Humo/Uzcard": "HUM"}[method]
            counter += 1
            payments.append(
                Payment(
                    txn_id=f"TRX-{created.year}-{counter:05d}",
                    member=member,
                    user_display_name=member.name,
                    months=months,
                    amount=PLAN_PRICES[months],
                    method=method,
                    status=status_choice,
                    psp_ref=f"{prefix}-{random.randint(10_000_000, 99_999_999)}",
                    period_start=created.date(),
                    period_end=created.date() + timedelta(days=30 * months),
                    refund_reason=random.choice(
                        ["Foydalanuvchi so'rovi", "Texnik xatolik", "Ikki marta to'langan"]
                    )
                    if status_choice == PaymentStatus.REFUNDED
                    else "",
                    refunded_at=created + timedelta(hours=random.randint(1, 48))
                    if status_choice == PaymentStatus.REFUNDED
                    else None,
                    created_at=created,
                )
            )

        Payment.objects.bulk_create(payments, batch_size=500)
        self.stdout.write(f"{len(payments)} to'lov yaratildi.")

    # ------------------------------------------------------------------
    def _create_transactions(self, businesses, members):
        now = timezone.now()
        approved = [b for b in businesses if b.status == BusinessStatus.APPROVED]
        member_sample = random.sample(members, min(1500, len(members)))
        aziz = next((m for m in members if m.member_code == "123456789"), None)

        transactions = []

        # Aziz's visits at Baraka Restoran (design: business To'lovlar tarixi tab)
        baraka = next((b for b in approved if b.name == "Baraka Restoran"), None)
        if baraka and aziz:
            for i, st in enumerate(
                [TransactionStatus.SUCCESS, TransactionStatus.SUCCESS, TransactionStatus.CANCELLED, TransactionStatus.SUCCESS]
            ):
                transactions.append(
                    BusinessTransaction(
                        business=baraka,
                        member=aziz,
                        member_name=aziz.name,
                        cashier="Dilnoza.X",
                        original_amount=50_000,
                        final_amount=37_500,
                        status=st,
                        created_at=now - timedelta(hours=i * 2 + 1, minutes=random.randint(0, 50)),
                    )
                )

        # Bulk QR transactions over the last 60 days
        for _ in range(6_000):
            b = random.choice(approved)
            m = random.choice(member_sample)
            lo, hi = BILL_RANGE[b.category]
            original = random.randint(lo // 1000, hi // 1000) * 1000
            final = int(original * (100 - b.discount_percent) / 100)
            hour_weights = [1] * 9 + [3, 3, 4, 5, 4, 3, 3, 4, 6, 8, 7, 5, 3, 2, 1]
            hour = random.choices(range(24), weights=hour_weights[:24])[0]
            created = now - timedelta(days=random.randint(0, 60))
            created = created.replace(hour=hour, minute=random.randint(0, 59))
            transactions.append(
                BusinessTransaction(
                    business=b,
                    member=m,
                    member_name=m.name,
                    cashier=random.choice(CASHIERS),
                    original_amount=original,
                    final_amount=final,
                    status=random.choices(
                        [TransactionStatus.SUCCESS, TransactionStatus.CANCELLED], weights=[0.94, 0.06]
                    )[0],
                    created_at=created,
                )
            )

        BusinessTransaction.objects.bulk_create(transactions, batch_size=500)
        self.stdout.write(f"{len(transactions)} tranzaksiya yaratildi.")

    # ------------------------------------------------------------------
    def _create_applications(self):
        now = timezone.now()
        apps = []

        named = [
            ("Baraka Restoran", BusinessCategory.RESTORAN, "+998 90 123 45 67", "Toshkent shahri", 15,
             ApplicationStatus.NEW, now.replace(hour=14, minute=22)),
            ("Fresh Cut Barber", BusinessCategory.BARBER, "+998 93 242 59 11", "Toshkent shahri", 10,
             ApplicationStatus.NEW, now.replace(hour=11, minute=5)),
            ("GreenFit Gym", BusinessCategory.FITNESS, "+998 97 700 12 34", "Toshkent viloyati", 20,
             ApplicationStatus.REVIEWING, now - timedelta(days=1, hours=3)),
            ("Milano Pizza", BusinessCategory.RESTORAN, "+998 90 555 21 00", "Samarqand", 12,
             ApplicationStatus.CONTACTED, now - timedelta(days=1, hours=12)),
            ("Beauty Lab", BusinessCategory.SALON, "+998 88 302 77 65", "Buxoro", 15,
             ApplicationStatus.CREATED, now - timedelta(days=15)),
            ("Ocean Sushi", BusinessCategory.RESTORAN, "+998 91 400 88 22", "Toshkent shahri", 25,
             ApplicationStatus.REJECTED, now - timedelta(days=16)),
        ]
        for name, cat, phone, region, disc, st, created in named:
            apps.append(
                BusinessApplication(
                    business_name=name, category=cat, phone=phone, region=region,
                    discount_percent=disc, status=st, created_at=created,
                )
            )

        # Bulk: design counters — Barchasi 128 · Yangi 24 · Ko'rib chiqilmoqda 11 · Bog'lanildi 36
        statuses = (
            [ApplicationStatus.NEW] * 22
            + [ApplicationStatus.REVIEWING] * 10
            + [ApplicationStatus.CONTACTED] * 35
            + [ApplicationStatus.CREATED] * 40
            + [ApplicationStatus.REJECTED] * 15
        )
        for st in statuses:
            cat = random.choice(list(BusinessCategory.values))
            name = f"{random.choice(BUSINESS_NAME_POOL[cat])}"
            days = 0 if st == ApplicationStatus.NEW and random.random() < 0.4 else random.randint(1, 45)
            apps.append(
                BusinessApplication(
                    business_name=name,
                    category=cat,
                    phone=self._random_phone(),
                    region=random.choice(UZ_REGIONS[:8]),
                    discount_percent=random.choice([5, 10, 12, 15, 20, 25]),
                    status=st,
                    created_at=now - timedelta(days=days, hours=random.randint(0, 12)),
                )
            )

        BusinessApplication.objects.bulk_create(apps, batch_size=200)
        self.stdout.write(f"{len(apps)} ariza yaratildi.")

    # ------------------------------------------------------------------
    def _create_daily_activity(self):
        today = timezone.now().date()
        rows = []
        for i in range(365):
            day = today - timedelta(days=i)
            base = 780 + int(120 * random.random()) - (60 if day.weekday() >= 5 else 0)
            drift = int(i * 0.35)  # the app has been growing over time
            rows.append(
                DailyActivity(
                    date=day,
                    daily_active=847 if i == 0 else max(base - drift, 120),
                    qr_scans=random.randint(180, 420),
                    peak_hour=random.choices([12, 13, 17, 18, 18, 18, 19, 20], k=1)[0],
                )
            )
        DailyActivity.objects.bulk_create(rows, batch_size=500)
        self.stdout.write("Kunlik faollik yaratildi.")

    def _create_platform_stats(self):
        PlatformStat.objects.create(downloads=20_400, registrations=12_400, payment_page_opens=6_800)

    # ------------------------------------------------------------------
    def _create_notifications(self, members):
        premium_count = sum(1 for m in members if m.status == Status.PREMIUM)
        samples = [
            dict(
                title="Yangi barber salon ochildi!",
                body="Chilonzorda yangi hamkor barber salon ochildi! A'zolarimizga 25–35% chegirma. Bugun boring!",
                audience_type=AudienceType.CATEGORY,
                category=BusinessCategory.BARBER,
                language="uz",
                send_time="Hozir",
                delivered=len(members),
                hours_ago=1,
            ),
            dict(
                title="Premium tarifga 20% chegirma",
                body="Bugun kechgacha Premium obunaga 20% chegirma bilan foydalaning!",
                audience_type=AudienceType.ALL,
                category="",
                language="uz",
                send_time="19:00",
                delivered=len(members),
                hours_ago=26,
            ),
            dict(
                title="Obunangiz tugayapti",
                body="Obunangiz muddati tugashiga 3 kun qoldi, uzaytirishni unutmang.",
                audience_type=AudienceType.PREMIUM,
                category="",
                language="uz",
                send_time="20:00",
                delivered=premium_count,
                hours_ago=50,
            ),
        ]
        now = timezone.now()
        for s in samples:
            hours = s.pop("hours_ago")
            delivered = s.pop("delivered")
            n = Notification.objects.create(
                **s, delivered=delivered, opened=int(delivered * 0.72)
            )
            Notification.objects.filter(pk=n.pk).update(sent_at=now - timedelta(hours=hours))

    # ------------------------------------------------------------------
    def _create_alerts(self):
        now = timezone.now()
        rows = [
            (AdminAlertKind.MEMBER_JOINED, "Aziz Karimov a'zo bo'ldi", "", 5),
            (AdminAlertKind.BUSINESS_APPROVED, "Fresh Cut Barber tasdiqlandi", "", 23),
            (AdminAlertKind.PUSH_SENT, "Push xabar 4,891 ga yuborildi", "Yangi barber salon ochildi!", 120),
            (AdminAlertKind.MEMBER_JOINED, "Malika Yusupova a'zo bo'ldi", "", 300),
        ]
        for kind, title, body, minutes_ago in rows:
            a = AdminAlert.objects.create(kind=kind, title=title, body=body)
            AdminAlert.objects.filter(pk=a.pk).update(created_at=now - timedelta(minutes=minutes_ago))
        self.stdout.write("Bildirishnomalar (bell) yaratildi.")
