"""ESKI BUYRUQ — endi HECH NARSA QILMAYDI (ataylab).

TARIX / NEGA O'CHIRILGAN
------------------------
Ilgari bu buyruq deploy'ning `startCommand`ida turardi va `SEED` env
o'zgaruvchisiga qarab bazani TOZALAB qayta to'ldirardi:

    SEED=fake   -> seed_fake --fresh   (flush + soxta ma'lumot)
    SEED=reset  -> seed_demo           (flush + faqat admin)

Muammo: `SEED` o'zgaruvchisi Railway'da bir marta qo'yilgach, uni qo'lda
o'chirmaguncha O'ZGARMAS bo'lib qolardi. Natijada HAR BIR DEPLOYDA baza
flush qilinib, real foydalanuvchilar kiritgan barcha yangi ma'lumotlar
yo'q bo'lib ketardi.

Endi demo ma'lumot faqat QO'LDA, Railway Console orqali boshqariladi:

    python manage.py seed_fake --fresh   # tozalab, soxta demo ma'lumot to'ldiradi
    python manage.py seed_demo           # hammasini o'chirib, faqat admin qoldiradi

Bu fayl o'chirilmadi, chunki Railway panelidagi (dashboard) eski `startCommand`
`railway.json`dan USTUN turadi. Agar o'sha yerda hali `run_seed` chaqirilayotgan
bo'lsa, buyruq mavjud bo'lmasa deploy "Unknown command" bilan yiqilardi.
Shuning uchun u zararsiz "no-op" sifatida qoldirildi — endi hech qanday
sharoitda ma'lumotni o'chirmaydi.
"""

import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Eskirgan: hech narsa qilmaydi. Demo ma'lumot uchun seed_fake / seed_demo ishlating."

    def handle(self, *args, **opts):
        line = "=" * 60
        seed_env = (os.environ.get("SEED") or "").strip()

        self.stdout.write(line)
        self.stdout.write(self.style.WARNING("[run_seed] Bu buyruq eskirgan va HECH NARSA QILMAYDI."))

        if seed_env:
            self.stdout.write(
                self.style.WARNING(
                    f"[run_seed] SEED={seed_env!r} env o'zgaruvchisi hali qo'yilgan, lekin "
                    "u ENDI E'TIBORGA OLINMAYDI — bazangiz xavfsiz."
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "[run_seed] Chalkashmaslik uchun uni Railway -> Variables'dan o'chirib "
                    "tashlang."
                )
            )

        self.stdout.write("[run_seed] Demo ma'lumot uchun Railway Console'da qo'lda ishlating:")
        self.stdout.write("             python manage.py seed_fake --fresh   # soxta ma'lumot")
        self.stdout.write("             python manage.py seed_demo           # hammasini tozalash")
        self.stdout.write(line)
