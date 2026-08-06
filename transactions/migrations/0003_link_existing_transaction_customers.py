"""Eski tranzaksiyalarni mijoz hisobiga bog'lash (bir martalik).

Kassir paneli ilgari tranzaksiya yaratganda mijozning hisobini ham,
telefon raqamini ham yubormasdi — shu sabab mijoz ilovasida "tejagan
summa" ko'rinmasdi. Bu migratsiya mavjud yozuvlarni imkon qadar tiklaydi:
telefon raqami bo'yicha, u bo'lmasa ism bo'yicha (faqat noaniqlik
bo'lmasa). Bir xil ismli bir nechta mijoz bo'lsa yozuvga TEGILMAYDI.

Xuddi shu mantiq `manage.py link_transaction_customers` buyrug'ida ham bor
(keyinchalik qo'lda ishlatish uchun).
"""

import re

from django.db import migrations


def _tail(phone):
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else ""


def _full_name(user):
    name = f"{user.first_name} {user.last_name}".strip()
    return (name or user.username or "").strip().lower()


def link_customers(apps, schema_editor):
    Transaction = apps.get_model("transactions", "Transaction")
    User = apps.get_model("users", "User")

    by_tail = {}
    by_name = {}
    for user in User.objects.filter(role="customer").only(
        "id", "phone_number", "first_name", "last_name", "username"
    ):
        tail = _tail(user.phone_number)
        if tail:
            by_tail.setdefault(tail, []).append(user)
        name = _full_name(user)
        if name:
            by_name.setdefault(name, []).append(user)

    for tx in Transaction.objects.filter(customer__isnull=True).iterator():
        match = None

        tail = _tail(tx.customer_phone)
        if tail:
            candidates = by_tail.get(tail, [])
            if len(candidates) == 1:
                match = candidates[0]

        if match is None:
            name = (tx.customer_name or "").strip().lower()
            candidates = by_name.get(name, []) if name else []
            if len(candidates) == 1:
                match = candidates[0]

        if match is None:
            continue

        tx.customer = match
        fields = ["customer"]
        if not tx.customer_phone and match.phone_number:
            tx.customer_phone = match.phone_number
            fields.append("customer_phone")
        tx.save(update_fields=fields)


def noop(apps, schema_editor):
    """Orqaga qaytarish: bog'lanishni uzish ma'lumot yo'qotmaydi, shu sabab
    hech narsa qilinmaydi."""


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0002_transaction_customer_and_more"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(link_customers, noop),
    ]
