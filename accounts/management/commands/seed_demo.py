"""Bazani tozalab (BARCHA ma'lumot o'chadi), faqat bitta admin operator qoldiradi.

Ishlatish (Railway Console yoki lokal):
    python manage.py seed_demo
    python manage.py seed_demo --login boss --password 'Zor2024!' --email boss@savin.uz
    python manage.py seed_demo --keep-data      # ma'lumotni o'chirmay, faqat admin

DIQQAT: `--keep-data` berilmasa, BARCHA jadvallardagi ma'lumot o'chiriladi
(Django `flush`). Migratsiya tarixi va jadval sxemasi saqlanadi — faqat qatorlar
o'chadi. So'ng admin panel operatori (accounts.AdminUser) yaratiladi; biznes/kassir
paneli `users.User`dan foydalanadi va bu buyruq unda hech kim qoldirmaydi.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from accounts.models import AccountSettings, AdminUser, NotificationPreference


class Command(BaseCommand):
    help = "Barcha ma'lumotni o'chirib (flush), faqat bitta admin yaratadi."

    def add_arguments(self, parser):
        parser.add_argument("--login", default="admin", help="Admin login (default: admin).")
        parser.add_argument(
            "--password", default="admin12345", help="Admin parol (default: admin12345)."
        )
        parser.add_argument("--email", default="admin@savin.uz", help="Admin email.")
        parser.add_argument(
            "--keep-data",
            action="store_true",
            help="Ma'lumotni o'chirmaydi — faqat adminni yaratadi/yangilaydi.",
        )

    def handle(self, *args, **opts):
        if not opts["keep_data"]:
            self.stdout.write(self.style.WARNING("!  Barcha ma'lumot o'chirilyapti (flush)..."))
            call_command("flush", "--noinput")
            self.stdout.write(self.style.SUCCESS("OK Baza tozalandi."))

        login = opts["login"]
        password = opts["password"]

        admin = AdminUser.objects.filter(username=login).first()
        if admin:
            admin.email = opts["email"]
            admin.first_name = admin.first_name or "Admin"
            admin.is_staff = True
            admin.is_superuser = True
            admin.is_active = True
            admin.set_password(password)
            admin.save()
            self.stdout.write(
                self.style.WARNING(f"'{login}' mavjud edi — parol va huquqlar yangilandi.")
            )
        else:
            admin = AdminUser.objects.create_superuser(
                username=login,
                email=opts["email"],
                password=password,
                first_name="Admin",
            )
            self.stdout.write(self.style.SUCCESS("OK Yangi admin yaratildi."))

        NotificationPreference.objects.get_or_create(user=admin)
        AccountSettings.objects.get_or_create(user=admin)

        line = "=" * 46
        self.stdout.write(self.style.SUCCESS(line))
        self.stdout.write(self.style.SUCCESS(f"  Admin panel login : {login}"))
        self.stdout.write(self.style.SUCCESS(f"  Parol             : {password}"))
        self.stdout.write(self.style.SUCCESS(line))
