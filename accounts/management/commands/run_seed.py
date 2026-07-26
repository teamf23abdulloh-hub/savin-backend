"""Deploy vaqtida SEED env-o'zgaruvchisiga qarab demo ma'lumotni boshqaradi.

Bu buyruq startCommand'da (railway.json / Procfile) `migrate`dan keyin ishlaydi,
ya'ni RUNTIME'da — Postgres mavjud. Console kerak emas: Railway'da faqat
`SEED` o'zgaruvchisini qo'yib, servisni Redeploy qilasiz.

    SEED=fake   -> barcha ma'lumotni tozalab, realistik demo bilan to'ldiradi (seed_fake --fresh)
    SEED=reset  -> barcha ma'lumotni o'chirib, faqat admin qoldiradi (seed_demo)
    (bo'sh/boshqa) -> hech narsa qilmaydi

Natija va (agar bo'lsa) XATO to'liq deploy logiga chiqadi. Buyruq HECH QACHON
deploy'ni yiqitmaydi — xato bo'lsa ham gunicorn ishga tushaveradi.

Ishlatib bo'lgach, takror-seedni to'xtatish uchun SEED'ni `off` qiling yoki o'chiring.
"""

import os
import traceback

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "SEED env qiymatiga qarab demo ma'lumot yaratadi/tozalaydi (deploy'da avtomatik)."

    def handle(self, *args, **opts):
        mode = (os.environ.get("SEED") or "").strip().lower()
        line = "=" * 56
        self.stdout.write(line)
        self.stdout.write(f"[run_seed] SEED = {mode!r}")

        if mode not in ("fake", "reset"):
            self.stdout.write("[run_seed] 'fake' yoki 'reset' emas — o'tkazib yuborildi.")
            self.stdout.write(line)
            return

        try:
            if mode == "fake":
                call_command("seed_fake", "--fresh")
            else:  # reset
                call_command("seed_demo")
            self.stdout.write(self.style.SUCCESS(f"[run_seed] '{mode}' MUVAFFAQIYATLI bajarildi."))
        except Exception:
            # Deploy yiqilmasin — xatoni logga to'liq chiqaramiz.
            self.stdout.write(self.style.ERROR("[run_seed] XATO YUZ BERDI! To'liq traceback:"))
            self.stdout.write(traceback.format_exc())

        self.stdout.write(line)
