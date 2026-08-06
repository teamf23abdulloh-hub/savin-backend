"""Eski tranzaksiyalarni mijoz hisobiga bog'lash.

Kassir paneli ilgari tranzaksiya yaratganda mijozning hisobini ham,
telefon raqamini ham yubormasdi. Natijada bu yozuvlar hech kimga tegishli
bo'lmay qolgan va mijoz ilovasida "tejagan summa" ko'rinmagan.

Buyruq shu yozuvlarni imkon qadar tiklaydi:
  1) telefon raqami bor bo'lsa — oxirgi 9 raqam bo'yicha,
  2) aks holda mijoz ismi bo'yicha, lekin FAQAT shu ism bitta mijozga
     tegishli bo'lsa (noaniqlik bo'lsa tegilmaydi).

Ishlatish:
    python manage.py link_transaction_customers --dry-run
    python manage.py link_transaction_customers
"""

import re

from django.core.management.base import BaseCommand

from transactions.models import Transaction
from users.models import User


def _tail(phone):
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else ""


class Command(BaseCommand):
    help = "Mijozga bog'lanmagan tranzaksiyalarni telefon yoki ism bo'yicha tiklaydi"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Hech narsa saqlanmaydi — faqat nima o'zgarishi ko'rsatiladi",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        customers = list(
            User.objects.filter(role=User.Role.CUSTOMER).only(
                "id", "phone_number", "first_name", "last_name", "username"
            )
        )

        by_tail = {}
        by_name = {}
        for user in customers:
            tail = _tail(user.phone_number)
            if tail:
                by_tail.setdefault(tail, []).append(user)
            name = (user.get_full_name() or user.username or "").strip().lower()
            if name:
                by_name.setdefault(name, []).append(user)

        pending = Transaction.objects.filter(customer__isnull=True)
        total = pending.count()
        linked_by_phone = linked_by_name = skipped = 0

        for tx in pending.iterator():
            match = None

            tail = _tail(tx.customer_phone)
            if tail:
                candidates = by_tail.get(tail, [])
                if len(candidates) == 1:
                    match = candidates[0]
                    linked_by_phone += 1

            if match is None:
                name = (tx.customer_name or "").strip().lower()
                candidates = by_name.get(name, []) if name else []
                # Noaniqlik bo'lsa tegmaymiz — noto'g'ri mijozga yozib
                # qo'yishdan ko'ra bog'lamay qoldirgan yaxshiroq.
                if len(candidates) == 1:
                    match = candidates[0]
                    linked_by_name += 1

            if match is None:
                skipped += 1
                continue

            if not dry_run:
                tx.customer = match
                if not tx.customer_phone and match.phone_number:
                    tx.customer_phone = match.phone_number
                tx.save(update_fields=["customer", "customer_phone"])

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Jami bog'lanmagan: {total} | "
                f"telefon bo'yicha: {linked_by_phone} | "
                f"ism bo'yicha: {linked_by_name} | "
                f"tegilmadi: {skipped}"
            )
        )
