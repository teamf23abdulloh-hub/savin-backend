"""Barcha panellar bo'sh ko'rinmasligi uchun realistik SOXTA (demo) ma'lumot to'ldiradi.

Ishlatish (Railway Console yoki lokal):
    python manage.py seed_fake                 # mavjud ma'lumot ustiga qo'shadi
    python manage.py seed_fake --fresh         # avval BARCHA ma'lumotni o'chirib, keyin to'ldiradi
    python manage.py seed_fake --fresh --businesses 15 --customers 60 --transactions 600

Nima yaratadi:
  * Admin operator (accounts.AdminUser)           -> login: admin / admin12345
  * Kategoriyalar, bizneslar, egalar, kassirlar, mijozlar (users.User)
  * Xizmatlar, arizalar (Arizalar paneli), tranzaksiyalar (Chegirmalar tarixi)
  * Chegirma qo'llanishlari, chegirma o'zgartirish so'rovlari
  * To'lovlar (Click/Payme/Uzum/Karta), bildirishnomalar
  * Kunlik analitika snapshotlari (grafikalar uchun, ~60 kun)

Barcha soxta foydalanuvchilar paroli: demo12345
Biznes/kassir paneliga kirish uchun namuna loginlar buyruq oxirida chop etiladi.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from accounts.models import AccountSettings, AdminUser, NotificationPreference
from analytics.models import CategoryActivityStat, DailyStatSnapshot
from businesses.models import (
    Application,
    Business,
    BusinessType,
    Cashier,
    Category,
    Region,
    Service,
)
from discounts.models import DiscountChangeRequest, DiscountUsage
from notifications.models import PushNotification, UserNotification
from payments.models import Payment
from transactions.models import DailyTransactionStat, Transaction
from users.models import Membership, User

FIRST_NAMES = [
    "Aziz", "Bekzod", "Dilnoza", "Jasur", "Kamola", "Laziz", "Madina", "Nodir",
    "Oybek", "Rustam", "Sardor", "Shahnoza", "Umar", "Zarina", "Firuza", "Bobur",
    "Gulnora", "Hasan", "Iroda", "Javohir", "Malika", "Sanjar", "Nigora", "Otabek",
    "Dilshod", "Sevara", "Aziza", "Farrux", "Kamron", "Nilufar",
]
LAST_NAMES = [
    "Karimov", "Rustamov", "Yusupova", "Tosheva", "Ergashev", "Aliyev", "Saidova",
    "Nazarov", "Qodirov", "Ismoilova", "Xolmatov", "Yo'ldosheva", "Abdullayev",
    "Rahimova", "Tursunov", "Sultonova", "Mirzayev", "Umarova", "Jo'rayev", "G'ofurova",
]

CATEGORIES = [
    ("Kafe va Restoran", "kafe-restoran"),
    ("Go'zallik saloni", "gozallik-saloni"),
    ("Kiyim do'koni", "kiyim-dokoni"),
    ("Oziq-ovqat", "oziq-ovqat"),
    ("Elektronika", "elektronika"),
    ("Farmatsevtika", "farmatsevtika"),
    ("Sport zali", "sport-zali"),
    ("Avtoservis", "avtoservis"),
    ("Kitob do'koni", "kitob-dokoni"),
    ("Bolalar dunyosi", "bolalar-dunyosi"),
]

BUSINESS_PREFIXES = [
    "Osma", "Baraka", "Zamin", "Oltin", "Yulduz", "Diyor", "Sharq", "Bahor",
    "Zilol", "Marvarid", "Chinor", "Anhor", "Lazzat", "Milliy", "Grand",
]

SERVICE_POOL = {
    "Kafe va Restoran": ["Biznes-lanch", "Osh", "Lag'mon", "Shashlik", "Coffee", "Desert"],
    "Go'zallik saloni": ["Soch olish", "Manikur", "Pedikur", "Makiyaj", "Kosa", "Massaj"],
    "Kiyim do'koni": ["Ko'ylak", "Shim", "Kurtka", "Poyabzal", "Aksessuar", "Sumka"],
    "Oziq-ovqat": ["Non", "Sut mahsulotlari", "Go'sht", "Mevalar", "Ichimlik", "Shirinlik"],
    "Elektronika": ["Telefon ta'miri", "Noutbuk", "Quloqchin", "Zaryadchi", "Aksessuar", "Smart soat"],
    "Farmatsevtika": ["Dori", "Vitamin", "Bandaj", "Termometr", "Maska", "Antiseptik"],
    "Sport zali": ["1 oylik abonement", "Shaxsiy trener", "Basseyn", "Yoga", "Bokschilik", "Fitnes"],
    "Avtoservis": ["Moy almashtirish", "Yuvish", "Diagnostika", "Shina", "Tormoz", "Akkumulyator"],
    "Kitob do'koni": ["Badiiy kitob", "Darslik", "Kanselyariya", "Bloknot", "Ruchka", "Globus"],
    "Bolalar dunyosi": ["O'yinchoq", "Kiyim", "Aravacha", "Kitobcha", "Konstruktor", "Velosiped"],
}

REGIONS = [r.value for r in Region]
PROVIDERS = [p.value for p in Payment.Provider]


def rand_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def rand_phone():
    return "+998" + str(random.randint(900000000, 999999999))


class Command(BaseCommand):
    help = "Realistik soxta (demo) ma'lumot to'ldiradi: bizneslar, tranzaksiyalar, to'lovlar va h.k."

    def add_arguments(self, parser):
        parser.add_argument("--fresh", action="store_true", help="Avval BARCHA ma'lumotni o'chiradi (flush).")
        parser.add_argument("--businesses", type=int, default=8)
        parser.add_argument("--customers", type=int, default=25)
        parser.add_argument("--transactions", type=int, default=150)
        parser.add_argument("--seed", type=int, default=42, help="Random urug'i (takrorlanuvchanlik uchun).")

    def handle(self, *args, **opts):
        random.seed(opts["seed"])

        # flush ATOMIC blokidan TASHQARIDA bo'lishi kerak (Postgres'da flush o'z
        # tranzaksiyasini boshqaradi).
        if opts["fresh"]:
            self.stdout.write(self.style.WARNING("!  Barcha ma'lumot o'chirilyapti (flush)..."))
            call_command("flush", "--noinput")
            self.stdout.write(self.style.SUCCESS("OK Baza tozalandi."))
        elif Business.objects.exists():
            # Idempotent: ma'lumot bo'lsa qayta yaratmaydi (deploy'da avtoseed uchun xavfsiz).
            self.stdout.write(self.style.WARNING(
                "Ma'lumot allaqachon mavjud — seed o'tkazib yuborildi "
                "(qayta to'ldirish uchun: seed_fake --fresh)."
            ))
            return

        self._seed(opts)

    @db_transaction.atomic
    def _seed(self, opts):
        now = timezone.now()
        # Barcha demo userlar paroli bir xil — hashni BIR MARTA hisoblab, hammaga
        # beramiz (har biriga alohida PBKDF2 hashlash juda sekin bo'lardi).
        demo_pw = make_password("demo12345")

        # ---- Admin operator ----
        admin, created = AdminUser.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@savin.uz", "is_staff": True, "is_superuser": True, "first_name": "Admin"},
        )
        admin.set_password("admin12345")
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        NotificationPreference.objects.get_or_create(user=admin)
        AccountSettings.objects.get_or_create(user=admin)

        # ---- Kategoriyalar ----
        categories = []
        for name, slug in CATEGORIES:
            cat, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name, "is_active": True})
            categories.append(cat)
        self.stdout.write(f"Kategoriyalar: {len(categories)}")

        # ---- Mijozlar (customers) ----
        customers = []
        base = User.objects.count()
        for i in range(opts["customers"]):
            u = User(
                username=f"customer{base + i + 1}",
                email=f"customer{base + i + 1}@mijoz.uz",
                first_name=random.choice(FIRST_NAMES),
                last_name=random.choice(LAST_NAMES),
                phone_number=rand_phone(),
                role=User.Role.CUSTOMER,
            )
            u.password = demo_pw
            u.save()
            Membership.objects.create(
                user=u,
                status=random.choice([Membership.Status.ACTIVE, Membership.Status.ACTIVE, Membership.Status.EXPIRED]),
                expires_at=now + timedelta(days=random.randint(-30, 300)),
            )
            customers.append(u)
        self.stdout.write(f"Mijozlar: {len(customers)}")

        # ---- Bizneslar + egalar + kassirlar + xizmatlar ----
        businesses = []
        cashiers_by_biz = {}
        owner_logins, cashier_logins = [], []
        obase = User.objects.filter(role=User.Role.BUSINESS_OWNER).count()

        for i in range(opts["businesses"]):
            cat = random.choice(categories)
            biz_name = f"{random.choice(BUSINESS_PREFIXES)} {cat.name.split()[0]}"
            owner_login = f"owner{obase + i + 1}@savin.uz"
            owner = User(
                username=f"owner{obase + i + 1}",
                email=owner_login,
                first_name=random.choice(FIRST_NAMES),
                last_name=random.choice(LAST_NAMES),
                phone_number=rand_phone(),
                role=User.Role.BUSINESS_OWNER,
            )
            owner.password = demo_pw
            owner.save()
            Membership.objects.create(user=owner, status=Membership.Status.ACTIVE,
                                      expires_at=now + timedelta(days=random.randint(30, 365)))
            owner_logins.append(owner_login)

            region = random.choice(REGIONS)
            btype = random.choice([BusinessType.YATT, BusinessType.MCHJ])

            # Tasdiqlangan ariza (Arizalar panelida ko'rinadi)
            app = Application.objects.create(
                applicant=owner,
                business_name=biz_name,
                category=cat,
                business_type=btype,
                responsible_full_name=f"{owner.first_name} {owner.last_name}",
                short_description=f"{biz_name} — sifatli xizmat.",
                phone_number=rand_phone(),
                email=owner_login,
                region=region,
                city_district="Chilonzor tumani",
                full_address="Bunyodkor ko'chasi, 12-uy",
                discount_percent=random.choice([5, 10, 15, 20, 25]),
                status=Application.Status.APPROVED,
                current_step=4,
                panel_login=owner_login,
                panel_password="demo12345",
                reviewed_at=now - timedelta(days=random.randint(10, 90)),
            )

            biz = Business.objects.create(
                owner=owner,
                application=app,
                name=biz_name,
                category=cat,
                business_type=btype,
                description=f"{biz_name} — {cat.name} sohasida.",
                phone_number=rand_phone(),
                email=owner_login,
                region=region,
                city_district="Chilonzor tumani",
                full_address="Bunyodkor ko'chasi, 12-uy",
                partnership_status=random.choice([
                    Business.PartnershipStatus.ACTIVE, Business.PartnershipStatus.ACTIVE,
                    Business.PartnershipStatus.PAUSED,
                ]),
                contract_signed=True,
                is_active=True,
            )
            businesses.append(biz)

            # Xizmatlar
            for sname in SERVICE_POOL.get(cat.name, ["Xizmat 1", "Xizmat 2", "Xizmat 3"]):
                Service.objects.create(
                    business=biz, name=sname,
                    price=Decimal(random.randrange(20000, 500000, 5000)),
                    is_active=True,
                )

            # Kassirlar (2-3 ta)
            biz_cashiers = []
            for c in range(random.randint(2, 3)):
                clogin = f"cashier{obase * 3 + i * 3 + c + 1}@savin.uz"
                cuser = User(
                    username=f"cashier{obase * 3 + i * 3 + c + 1}",
                    email=clogin,
                    first_name=random.choice(FIRST_NAMES),
                    last_name=random.choice(LAST_NAMES),
                    phone_number=rand_phone(),
                    role=User.Role.CASHIER,
                )
                cuser.password = demo_pw
                cuser.save()
                cashier = Cashier.objects.create(
                    business=biz, user=cuser,
                    full_name=f"{cuser.first_name} {cuser.last_name}", is_active=True,
                )
                biz_cashiers.append((cashier, cuser))
                cashier_logins.append(clogin)
            cashiers_by_biz[biz.id] = biz_cashiers

        self.stdout.write(f"Bizneslar: {len(businesses)} | egalar + kassirlar yaratildi")

        # ---- Kutilayotgan / rad etilgan arizalar (Arizalar paneli boy ko'rinishi uchun) ----
        for st in [Application.Status.PENDING, Application.Status.PENDING, Application.Status.REJECTED]:
            cat = random.choice(categories)
            Application.objects.create(
                business_name=f"{random.choice(BUSINESS_PREFIXES)} {cat.name.split()[0]}",
                category=cat,
                business_type=random.choice([BusinessType.YATT, BusinessType.MCHJ]),
                responsible_full_name=rand_name(),
                phone_number=rand_phone(),
                region=random.choice(REGIONS),
                city_district="Yunusobod tumani",
                full_address="Amir Temur shoh ko'chasi, 5",
                discount_percent=random.choice([10, 15, 20]),
                status=st,
                current_step=random.randint(2, 4),
                rejection_reason="Hujjatlar to'liq emas." if st == Application.Status.REJECTED else None,
            )

        # ---- Tranzaksiyalar (Chegirmalar tarixi) — bulk_create + backdate ----
        tx_objs, tx_dates = [], []
        for _ in range(opts["transactions"]):
            biz = random.choice(businesses)
            biz_cashiers = cashiers_by_biz[biz.id]
            _, cuser = random.choice(biz_cashiers)
            svc = random.choice(list(biz.services.all()))
            base_price = svc.price
            dperc = random.choice([5, 10, 10, 15, 15, 20, 25])
            disc_amt = (base_price * dperc) / Decimal(100)
            final = base_price - disc_amt
            cust = random.choice(customers)
            tx_objs.append(Transaction(
                business=biz, cashier=cuser,
                customer_name=f"{cust.first_name} {cust.last_name}",
                customer_phone=cust.phone_number,
                service_name=svc.name, service_category=biz.category.name,
                base_price=base_price, discount_percent=dperc,
                discount_amount=disc_amt, final_price=final,
                status=random.choice(["completed", "completed", "completed", "cancelled", "refunded"]),
            ))
            tx_dates.append(now - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23),
                                            minutes=random.randint(0, 59)))
        Transaction.objects.bulk_create(tx_objs)
        for obj, dt in zip(tx_objs, tx_dates):
            obj.created_at = dt
        Transaction.objects.bulk_update(tx_objs, ["created_at"])
        self.stdout.write(f"Tranzaksiyalar: {len(tx_objs)}")

        # ---- Chegirma qo'llanishlari (DiscountUsage) ----
        du_objs, du_dates = [], []
        for _ in range(int(opts["transactions"] * 0.7)):
            biz = random.choice(businesses)
            cashier, _ = random.choice(cashiers_by_biz[biz.id])
            amount = Decimal(random.randrange(30000, 600000, 5000))
            perc = random.choice([5, 10, 15, 20])
            du_objs.append(DiscountUsage(
                business=biz, customer=random.choice(customers), cashier=cashier,
                applied_percent=perc, purchase_amount=amount,
                discount_amount=(amount * perc) / Decimal(100),
            ))
            du_dates.append(now - timedelta(days=random.randint(0, 60)))
        DiscountUsage.objects.bulk_create(du_objs)
        for obj, dt in zip(du_objs, du_dates):
            obj.used_at = dt
        DiscountUsage.objects.bulk_update(du_objs, ["used_at"])
        self.stdout.write(f"Chegirma qo'llanishlari: {len(du_objs)}")

        # ---- Chegirma o'zgartirish so'rovlari (Admin tasdig'i uchun) ----
        for biz in random.sample(businesses, min(5, len(businesses))):
            old = random.choice([10, 15, 20])
            DiscountChangeRequest.objects.create(
                business=biz, requested_by=biz.owner, old_percent=old,
                new_percent=old + 5, reason="Bayram aksiyasi uchun foizni oshirish.",
                status=random.choice([DiscountChangeRequest.Status.PENDING,
                                      DiscountChangeRequest.Status.APPROVED]),
            )

        # ---- To'lovlar (Payment) ----
        pay_objs, pay_dates = [], []
        allpayusers = [b.owner for b in businesses] + customers
        for _ in range(int(opts["transactions"] * 0.5)):
            st = random.choice([Payment.Status.SUCCESS] * 6 + [Payment.Status.FAILED, Payment.Status.PENDING,
                                                               Payment.Status.REFUNDED])
            pay_objs.append(Payment(
                user=random.choice(allpayusers),
                amount=Decimal(random.randrange(19000, 199000, 1000)),
                provider=random.choice(PROVIDERS),
                provider_transaction_id=f"TX{random.randint(10**9, 10**10)}",
                status=st,
                failure_reason="Mablag' yetarli emas." if st == Payment.Status.FAILED else None,
            ))
            pay_dates.append(now - timedelta(days=random.randint(0, 60)))
        Payment.objects.bulk_create(pay_objs)
        for obj, dt in zip(pay_objs, pay_dates):
            obj.created_at = dt
        Payment.objects.bulk_update(pay_objs, ["created_at"])
        self.stdout.write(f"To'lovlar: {len(pay_objs)}")

        # ---- Bildirishnomalar ----
        for i in range(6):
            PushNotification.objects.create(
                created_by=admin if False else businesses[0].owner,  # AUTH_USER_MODEL FK
                audience=random.choice([PushNotification.Audience.ALL, PushNotification.Audience.CATEGORY]),
                target_category=random.choice(categories),
                title_uz=f"Aksiya #{i + 1}", body_uz="Savin bilan yangi chegirmalarni kashf eting!",
                status=random.choice([PushNotification.Status.SENT, PushNotification.Status.SCHEDULED]),
                sent_at=now - timedelta(days=random.randint(1, 20)),
            )
        for cust in random.sample(customers, min(25, len(customers))):
            UserNotification.objects.create(
                user=cust,
                notification_type=random.choice(list(UserNotification.NotificationType)),
                title="Yangi chegirma!", body="Sizga yaqin bizneslarda yangi chegirmalar bor.",
                is_read=random.choice([True, False]),
            )

        # ---- Kunlik analitika snapshotlari (grafikalar uchun) — bulk ----
        # SEED=fake --fresh bilan ishlaydi (baza tozalangan), shuning uchun
        # bulk_create xavfsiz: sana/kategoriya juftliklari takrorlanmaydi.
        snap_objs, cat_stat_objs = [], []
        for d in range(60):
            day = (now - timedelta(days=d)).date()
            dau = random.randint(40, 120) + (60 - d)
            paid = random.randint(5, 30)
            downloads = paid + random.randint(20, 80)
            snap_objs.append(DailyStatSnapshot(
                date=day, dau=dau, mau=dau * random.randint(4, 7),
                new_users=random.randint(3, 25), new_businesses=random.randint(0, 3),
                downloads_count=downloads, paid_count=paid,
                conversion_rate=Decimal(str(round(paid / downloads * 100, 2))),
                total_discount_amount=Decimal(random.randrange(500000, 5000000, 10000)),
                churned_users=random.randint(0, 8),
                churn_rate=Decimal(str(round(random.uniform(0.5, 5.0), 2))),
            ))
            for cat in random.sample(categories, 4):
                cat_stat_objs.append(CategoryActivityStat(
                    date=day, category=cat,
                    views_count=random.randint(20, 300), purchases_count=random.randint(2, 40),
                ))
        DailyStatSnapshot.objects.bulk_create(snap_objs)
        CategoryActivityStat.objects.bulk_create(cat_stat_objs)

        # ---- Kunlik biznes statistikasi (dashboard) — bulk ----
        biz_stat_objs = []
        for biz in businesses:
            for d in range(30):
                day = (now - timedelta(days=d)).date()
                cnt = random.randint(2, 25)
                base_amt = Decimal(cnt * random.randrange(30000, 120000, 5000))
                disc_amt = (base_amt * Decimal(random.randint(5, 20))) / Decimal(100)
                biz_stat_objs.append(DailyTransactionStat(
                    business=biz, date=day,
                    total_transactions=cnt, total_base_amount=base_amt,
                    total_discount_amount=disc_amt, total_final_amount=base_amt - disc_amt,
                    average_discount_percent=Decimal(random.randint(8, 18)),
                ))
        DailyTransactionStat.objects.bulk_create(biz_stat_objs)

        # ---- ADMIN PANEL (core app) — saven-admin AYNAN shulardan o'qiydi ----
        core_counts = self._seed_core(now)
        self.stdout.write(
            f"Admin (core): Member={core_counts['members']} Business={core_counts['businesses']} "
            f"Tranzaksiya={core_counts['transactions']} To'lov={core_counts['payments']} "
            f"Ariza={core_counts['applications']}"
        )

        # ---- Xulosa ----
        line = "=" * 54
        self.stdout.write(self.style.SUCCESS(line))
        self.stdout.write(self.style.SUCCESS("  SOXTA MA'LUMOT TAYYOR"))
        self.stdout.write(self.style.SUCCESS(line))
        self.stdout.write(self.style.SUCCESS("  Admin panel : admin / admin12345"))
        if owner_logins:
            self.stdout.write(self.style.SUCCESS(f"  Biznes egasi: {owner_logins[0]} / demo12345"))
        if cashier_logins:
            self.stdout.write(self.style.SUCCESS(f"  Kassir      : {cashier_logins[0]} / demo12345"))
        self.stdout.write(self.style.SUCCESS("  Barcha soxta userlar paroli: demo12345"))
        self.stdout.write(self.style.SUCCESS(line))
        self.stdout.write(self.style.SUCCESS(
            f"  [biznes/kassir] Bizneslar={len(businesses)}  Mijozlar={len(customers)}  "
            f"Tranzaksiya={len(tx_objs)}  To'lov={len(pay_objs)}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"  [admin panel]   Member={core_counts['members']}  Business={core_counts['businesses']}  "
            f"Tranzaksiya={core_counts['transactions']}  To'lov={core_counts['payments']}"
        ))
        self.stdout.write(self.style.SUCCESS(line))

    def _seed_core(self, now):
        """Admin panel (core app) modellarini to'ldiradi — saven-admin shulardan o'qiydi.

        core.* modellari biznes/kassir panelidagi `businesses.*`/`users.*` dan
        BUTUNLAY alohida (admin avval alohida backend edi). Shuning uchun admin
        panelda ma'lumot ko'rinishi uchun ayni shu jadvallar to'ldirilishi shart.
        """
        from core import models as cm

        today = now.date()
        cities = ["Toshkent shahri", "Samarqand", "Buxoro", "Andijon", "Farg'ona", "Namangan"]
        cats = [c.value for c in cm.BusinessCategory]
        btypes = [t.value for t in cm.BusinessType]

        # Funnel (singleton) — dashboard "downloads" va konversiya uchun
        cm.PlatformStat.objects.create(downloads=5200, registrations=3400, payment_page_opens=1900)

        # A'zolar (Foydalanuvchilar)
        member_statuses = [cm.Status.PREMIUM, cm.Status.PREMIUM, cm.Status.NEW, cm.Status.TRIAL, cm.Status.OVERDUE]
        members = []
        for i in range(35):
            joined = today - timedelta(days=random.randint(0, 60))
            st = random.choice(member_statuses)
            members.append(cm.Member(
                member_code=f"{100000000 + i}",
                name=rand_name(), phone=rand_phone(), city=random.choice(cities),
                status=st,
                activity_status=random.choice([cm.ActivityStatus.ACTIVE, cm.ActivityStatus.ACTIVE,
                                                cm.ActivityStatus.NEW, cm.ActivityStatus.INACTIVE]),
                joined_at=joined,
                savings_total=Decimal(random.randrange(0, 2000000, 10000)),
                membership_start=joined if st == cm.Status.PREMIUM else None,
                membership_end=(joined + timedelta(days=365)) if st == cm.Status.PREMIUM else None,
                months_subscribed=random.randint(0, 12),
                device=random.choice(["iPhone 14 · iOS 17.2", "Samsung S23 · Android 14", "Redmi Note 12"]),
                referral_code=f"REF{1000 + i}", referral_invited=random.randint(0, 3),
            ))
        cm.Member.objects.bulk_create(members)
        members = list(cm.Member.objects.all())

        # Bizneslar (core) — ko'pchiligi "Tasdiqlangan" (dashboard active_businesses uchun)
        biz_statuses = [cm.BusinessStatus.APPROVED] * 5 + [cm.BusinessStatus.PENDING, cm.BusinessStatus.REJECTED]
        core_bizzes = []
        for i in range(12):
            submitted = today - timedelta(days=random.randint(5, 120))
            st = random.choice(biz_statuses)
            core_bizzes.append(cm.Business(
                business_code=f"{200000000 + i}",
                name=f"{random.choice(BUSINESS_PREFIXES)} {random.choice(cats)}",
                category=random.choice(cats), business_type=random.choice(btypes),
                owner=rand_name(), phone=rand_phone(), email=f"biz{i}@savin.uz",
                region=random.choice(cities), district="Chilonzor tumani",
                address="Bunyodkor ko'chasi, 12",
                discount_percent=random.choice([5, 10, 15, 20, 25]),
                min_purchase=Decimal(random.randrange(0, 200000, 10000)),
                login=f"biz{i}", password="demo12345",
                status=st, submitted_at=submitted,
                registered_at=(submitted + timedelta(days=3)) if st == cm.BusinessStatus.APPROVED else None,
            ))
        cm.Business.objects.bulk_create(core_bizzes)
        core_bizzes = list(cm.Business.objects.all())
        approved = [b for b in core_bizzes if b.status == cm.BusinessStatus.APPROVED] or core_bizzes

        # Biznes tranzaksiyalari
        txs = []
        for _ in range(220):
            b = random.choice(approved)
            m = random.choice(members)
            orig = Decimal(random.randrange(30000, 600000, 5000))
            perc = random.choice([5, 10, 15, 20])
            final = orig - (orig * perc // 100)
            txs.append(cm.BusinessTransaction(
                business=b, member=m, member_name=m.name, cashier=rand_name(),
                original_amount=orig, final_amount=final,
                status=random.choice([cm.TransactionStatus.SUCCESS] * 6 + [cm.TransactionStatus.CANCELLED]),
                created_at=now - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23)),
            ))
        cm.BusinessTransaction.objects.bulk_create(txs)

        # Arizalar (landing'dan kelgan hamkorlik so'rovlari)
        app_statuses = [cm.ApplicationStatus.NEW, cm.ApplicationStatus.NEW, cm.ApplicationStatus.REVIEWING,
                        cm.ApplicationStatus.CONTACTED, cm.ApplicationStatus.APPROVED, cm.ApplicationStatus.REJECTED]
        apps = []
        for i in range(10):
            apps.append(cm.BusinessApplication(
                business_name=f"{random.choice(BUSINESS_PREFIXES)} {random.choice(cats)}",
                category=random.choice(cats), phone=rand_phone(),
                region=random.choice(cities), discount_percent=random.choice([10, 15, 20]),
                status=random.choice(app_statuses),
                created_at=now - timedelta(days=random.randint(0, 30)),
                responsible_name=rand_name(), business_type=random.choice(btypes),
                email=f"apply{i}@savin.uz",
            ))
        cm.BusinessApplication.objects.bulk_create(apps)

        # To'lovlar (obuna) — oxirgi 6 oyga taqsimlangan (oylik daromad grafigi uchun)
        methods = [m.value for m in cm.PaymentMethod]
        pay_statuses = [cm.PaymentStatus.SUCCESS] * 7 + [cm.PaymentStatus.PENDING, cm.PaymentStatus.REFUNDED]
        pays = []
        for i in range(160):
            m = random.choice(members)
            months = random.choice([1, 1, 1, 3, 6, 12])
            pays.append(cm.Payment(
                txn_id=f"TXN{1000000 + i}", member=m, user_display_name=m.name,
                months=months, amount=Decimal(months * 19000),
                method=random.choice(methods), status=random.choice(pay_statuses),
                psp_ref=f"REF-{random.randint(10000000, 99999999)}",
                created_at=now - timedelta(days=random.randint(0, 180), hours=random.randint(0, 23)),
            ))
        cm.Payment.objects.bulk_create(pays)

        # Bildirishnomalar
        for i in range(6):
            cm.Notification.objects.create(
                title=f"Aksiya #{i + 1}", body="Savin bilan yangi chegirmalarni kashf eting!",
                audience_type=random.choice([cm.AudienceType.ALL, cm.AudienceType.PREMIUM]),
                delivered=random.randint(500, 3000), opened=random.randint(100, 1500),
            )

        # Kunlik faollik (60 kun) — faollik grafiklari uchun
        acts = [cm.DailyActivity(
            date=today - timedelta(days=d),
            daily_active=random.randint(80, 400),
            qr_scans=random.randint(50, 600),
            peak_hour=random.choice([12, 13, 18, 19, 20]),
        ) for d in range(60)]
        cm.DailyActivity.objects.bulk_create(acts)

        # Admin ogohlantirishlari (qo'ng'iroq belgisi)
        for _ in range(5):
            cm.AdminAlert.objects.create(
                kind=random.choice([cm.AdminAlertKind.BUSINESS_APPLICATION, cm.AdminAlertKind.MEMBER_JOINED,
                                    cm.AdminAlertKind.PUSH_SENT]),
                title="Yangi hodisa", body="Admin paneli bildirishnomasi.",
                is_read=random.choice([True, False]),
            )

        return dict(members=len(members), businesses=len(core_bizzes),
                    transactions=len(txs), payments=len(pays), applications=len(apps))
