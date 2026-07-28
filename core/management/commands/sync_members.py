"""Mavjud mobil mijozlar uchun admin paneldagi `Member` yozuvlarini to'ldiradi.

Signal faqat yangi saqlanishlarda ishlaydi, shu sabab avval ro'yxatdan
o'tganlar uchun bir marta shu buyruq yurgiziladi:

    python manage.py sync_members            # ko'rish (o'zgartirmaydi)
    python manage.py sync_members --apply    # haqiqatda yozadi
"""

from django.core.management.base import BaseCommand

from core.sync import find_member_by_phone, sync_member_from_user
from users.models import User


class Command(BaseCommand):
    help = "Mobil mijozlarni admin paneldagi Foydalanuvchilar ro'yxati bilan sinxronlaydi"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Haqiqatda yozish (bo'lmasa faqat ko'rsatadi)",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        customers = User.objects.filter(role=User.Role.CUSTOMER).order_by("created_at")

        missing, no_phone, existing = [], [], 0
        for user in customers:
            phone = (user.phone_number or "").strip()
            if not phone:
                no_phone.append(user)
                continue
            if find_member_by_phone(phone) is None:
                missing.append(user)
            else:
                existing += 1

        self.stdout.write(f"Jami mijozlar          : {customers.count()}")
        self.stdout.write(f"Allaqachon ro'yxatda   : {existing}")
        self.stdout.write(f"Telefonsiz (o'tkazildi): {len(no_phone)}")
        self.stdout.write(f"Qo'shilishi kerak      : {len(missing)}")

        for user in missing:
            name = f"{user.first_name} {user.last_name}".strip() or user.email
            self.stdout.write(f"   + {user.phone_number}  {name}")

        if not apply_changes:
            self.stdout.write(self.style.WARNING("\nKo'rish rejimi — hech narsa yozilmadi. Yozish uchun: --apply"))
            return

        created_count = 0
        for user in missing:
            result = sync_member_from_user(user)
            if result and result[1]:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"\n{created_count} ta yozuv qo'shildi."))
