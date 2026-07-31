"""Xizmatlari yo'q bizneslarga kategoriyasiga mos standart xizmatlarni qo'shadi.

Yangi bizneslar tasdiqlanganda xizmatlar avtomatik yaratiladi
(`businesses/services.py` -> `approve_application`). Bu buyruq esa avval
tasdiqlangan bizneslar uchun bir marta yurgiziladi:

    python manage.py seed_services            # ko'rish (o'zgartirmaydi)
    python manage.py seed_services --apply    # haqiqatda yozadi
"""

from django.core.management.base import BaseCommand

from businesses.default_services import create_default_services, services_for_category
from businesses.models import Business, Service


class Command(BaseCommand):
    help = "Xizmatlari yo'q bizneslarga standart xizmat turlarini qo'shadi"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Haqiqatda yozish")
        parser.add_argument(
            "--quiet", action="store_true", help="Faqat natijani chiqaradi"
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        quiet = options["quiet"]

        with_services = set(
            Service.objects.values_list("business_id", flat=True).distinct()
        )
        missing = [
            b
            for b in Business.objects.select_related("category").all()
            if b.id not in with_services
        ]

        if quiet and not missing:
            return

        self.stdout.write(f"Jami bizneslar        : {Business.objects.count()}")
        self.stdout.write(f"Xizmatlari bor        : {len(with_services)}")
        self.stdout.write(f"Xizmat qo'shiladi     : {len(missing)}")

        for b in missing[:20]:
            cat = b.category.name if b.category_id else "—"
            count = len(services_for_category(cat))
            self.stdout.write(f"   + {b.name} ({cat}) -> {count} ta xizmat")
        if len(missing) > 20:
            self.stdout.write(f"   ... va yana {len(missing) - 20} ta")

        if not apply_changes:
            self.stdout.write(
                self.style.WARNING("\nKo'rish rejimi — yozish uchun: --apply")
            )
            return

        total = sum(create_default_services(b) for b in missing)
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{len(missing)} ta biznesga jami {total} ta xizmat qo'shildi."
            )
        )
