from django.core.management.base import BaseCommand

# `get_user_model()` endi `users.User`ni qaytaradi (mijoz/biznes egasi/kassir),
# admin panel operatori esa alohida model — shuning uchun to'g'ridan-to'g'ri
# AdminUser ishlatiladi.
from accounts.models import AccountSettings, AdminUser, NotificationPreference


class Command(BaseCommand):
    help = (
        "Birinchi admin hisobini yaratadi (login: admin, parol: admin12345). "
        "Agar bazada allaqachon kamida bitta admin bo'lsa, hech narsa yaratmaydi."
    )

    def add_arguments(self, parser):
        parser.add_argument("--login", default="admin", help="Yangi admin uchun login.")
        parser.add_argument("--password", default="admin12345", help="Yangi admin uchun parol.")
        parser.add_argument("--email", default="admin@savin.uz", help="Yangi admin uchun email.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Bazada boshqa adminlar bo'lsa ham, baribir yangisini yaratish.",
        )

    def handle(self, *args, **options):
        User = AdminUser

        if User.objects.exists() and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    "Bazada allaqachon admin(lar) mavjud, hech narsa yaratilmadi. "
                    "Majburan yaratish uchun --force parametridan foydalaning."
                )
            )
            return

        login = options["login"]
        if User.objects.filter(username=login).exists():
            self.stdout.write(self.style.WARNING(f"'{login}' logini bilan admin allaqachon mavjud."))
            return

        user = User.objects.create_superuser(
            username=login,
            email=options["email"],
            password=options["password"],
            first_name="Admin",
        )
        NotificationPreference.objects.create(user=user)
        AccountSettings.objects.create(user=user)

        self.stdout.write(self.style.SUCCESS(f"Admin yaratildi -> login: {login}, parol: {options['password']}"))
