"""SMS xizmatini tekshirish.

    python manage.py sms_test                    # faqat sozlamalar va aloqa
    python manage.py sms_test +998901234567      # sinov SMS ham yuboradi
    python manage.py sms_test +998901234567 --text "Salom"

Nima uchun kerak: SMS yuborilmasligining sababi odatda uchtadan biri —
kredensiallar muhitga tushmagan, parol/email noto'g'ri, yoki matn Eskiz'da
moderatsiyadan o'tmagan. Bu buyruq uchalasini ham ro'yxatdan o'tish oqimini
buzmasdan, bir ko'rinishda ajratib beradi.
"""

from django.core.management.base import BaseCommand

from mobileapi import sms


class Command(BaseCommand):
    help = "SMS sozlamalarini tekshiradi va raqam berilsa sinov SMS yuboradi."

    def add_arguments(self, parser):
        parser.add_argument(
            "phone",
            nargs="?",
            help="Sinov SMS yuboriladigan raqam, masalan +998901234567",
        )
        parser.add_argument(
            "--text",
            default="",
            help="Yuboriladigan matn (standart: OTP shabloni namunasi)",
        )

    def handle(self, *args, **options):
        info = sms.diagnostics()

        self.stdout.write(self.style.MIGRATE_HEADING("SMS sozlamalari"))
        for key in (
            "provider",
            "test_mode",
            "has_credentials",
            "credentials_source",
            "email_set",
            "password_set",
            "sender",
            "sms_dev_mode_raw",
            "test_text_fallback",
            "otp_in_response",
            "otp_template",
        ):
            self.stdout.write(f"  {key:<20} {info[key]}")
        self.stdout.write(f"  {'eskiz_env_names':<20} {info['eskiz_env_names']}")

        if info["otp_in_response"]:
            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR(
                    "  SMS_ALLOW_OTP_IN_RESPONSE YOQILGAN — SMS ketmasa tasdiqlash\n"
                    "  kodi API javobida ochiq qaytadi. Ro'yxatdan o'tish barcha\n"
                    "  raqamlar uchun ishlaydi, LEKIN istalgan odam istalgan raqam\n"
                    "  nomidan kira oladi. Eskiz shabloni tasdiqlangach o'chiring:\n"
                    "  mobileapi/sms_credentials.py -> SMS_ALLOW_OTP_IN_RESPONSE = \"\""
                )
            )

        if info["test_mode"]:
            self.stdout.write("")
            # Test rejimining IKKI xil sababi bor — qaysi biri ekanini aytmasak
            # foydalanuvchi qo'ygan kredensiallarini qayta-qayta tekshiraveradi.
            if not info["has_credentials"]:
                reason = (
                    "TEST REJIMI — SMS haqiqatda yuborilmaydi.\n"
                    "Sabab: ESKIZ_EMAIL / ESKIZ_PASSWORD qo'yilmagan.\n"
                    "Ularni `backend/.env` fayliga (yoki hosting Variables\n"
                    "bo'limiga) yozing."
                )
            else:
                reason = (
                    "TEST REJIMI — SMS haqiqatda yuborilmaydi.\n"
                    "Sabab: kredensiallar joyida, lekin SMS_DEV_MODE=True.\n"
                    "SMS ketishi uchun `backend/.env` dan shu satrni o'chiring."
                )
            self.stdout.write(self.style.WARNING(reason))

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Provayder bilan aloqa"))
        ok, message = sms.check_connection()
        self.stdout.write(f"  {self.style.SUCCESS(message) if ok else self.style.ERROR(message)}")

        if ok:
            self._account_report()

        phone = options.get("phone")
        if not phone:
            self.stdout.write("")
            self.stdout.write(
                "Sinov SMS yuborish uchun raqam bering: "
                "python manage.py sms_test +998901234567"
            )
            return

        number = sms.normalize_phone(phone)
        if not number:
            self.stdout.write(self.style.ERROR(f"Raqam noto'g'ri: {phone}"))
            return

        text = options["text"] or sms.otp_template().replace("{code}", "123456")
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"Sinov SMS -> {number}"))
        self.stdout.write(f"  Matn: {text}")

        if sms.send_sms(phone, text):
            self.stdout.write(self.style.SUCCESS("  Provayder xabarni qabul qildi."))
        else:
            self.stdout.write(
                self.style.ERROR(
                    "  Yuborilmadi. Aniq sabab yuqoridagi log satrlarida "
                    "(Eskiz javobi bilan birga)."
                )
            )

    def _account_report(self):
        """Eskiz hisobi holati — SMS ketmasligining eng ko'p uchraydigan sababi."""
        ok, data = sms.account_info()
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Eskiz hisobi"))
        if not ok:
            self.stdout.write(self.style.ERROR(f"  {data}"))
            return

        self.stdout.write(f"  {'nomi':<20} {data['name']}")
        self.stdout.write(f"  {'rol':<20} {data['role']}")
        self.stdout.write(f"  {'holat':<20} {data['status']}")
        self.stdout.write(f"  {'balans':<20} {data['balance']}")

        templates = data["templates"]
        self.stdout.write(f"  {'shablonlar':<20} {len(templates)} ta")
        for line in templates:
            self.stdout.write(f"    - {line}")

        if str(data["role"]).lower() == "test":
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "  Hisob \"test\" rolida: Eskiz o'z matningizni RAD ETADI\n"
                    "  (faqat \"Bu Eskiz dan test\" matni o'tadi). Hisobni\n"
                    "  faollashtirish uchun my.eskiz.uz orqali murojaat qiling."
                )
            )
        if not templates:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "  Tasdiqlangan shablon yo'q. my.eskiz.uz -> SMS -> Sozlamalar\n"
                    "  -> \"Mening matnlarim\" bo'limida OTP matnini moderatsiyaga\n"
                    "  yuboring, so'ng uni SMS_OTP_TEMPLATE ga AYNAN ko'chiring."
                )
            )
