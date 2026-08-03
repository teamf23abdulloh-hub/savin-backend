"""SMS / OTP oqimi testlari.

Tarmoqqa chiqilmaydi — Eskiz javoblari mock qilinadi. Maqsad: kod yuborish,
tekshirish va xatolarni halol qaytarish yo'llari buzilmasligi.
"""

import contextlib
import os
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from mobileapi import sms
from mobileapi.models import PhoneOtp
from users.models import User

PHONE = "+998901234567"

# Testlar sozlamaning IKKALA manbasidan ham mustaqil bo'lishi kerak:
# dasturchining `backend/.env` fayli va vaqtinchalik `sms_credentials.py`.
# Ikkalasida ham SMS_DEV_MODE yoki o'z shabloni turgan bo'lishi mumkin va
# natija mashinadan mashinaga o'zgarib ketardi.
CLEAN_SMS_ENV = {
    "ESKIZ_EMAIL": "",
    "ESKIZ_PASSWORD": "",
    "ESKIZ_SENDER": "",
    "SMS_DEV_MODE": "",
    "SMS_OTP_TEMPLATE": "",
    "ESKIZ_TEST_TEXT_FALLBACK": "",
    "SMS_ALLOW_OTP_IN_RESPONSE": "",
}


@contextlib.contextmanager
def sms_env(**values):
    """Toza SMS muhiti: faqat berilgan qiymatlar ishlaydi."""
    env = dict(CLEAN_SMS_ENV)
    env.update(values)
    with mock.patch.dict(os.environ, env, clear=False):
        # Vaqtinchalik kredensial fayli testlarga aralashmasin
        with mock.patch.object(sms, "_from_file", return_value=""):
            yield


def eskiz_env(**extra):
    """Haqiqiy rejimni yoqadigan muhit (test uchun)."""
    return sms_env(ESKIZ_EMAIL="test@savin.uz", ESKIZ_PASSWORD="secret", **extra)


def no_sms_env():
    """Kredensiallarsiz muhit — test rejimi."""
    return sms_env()


class NormalizePhoneTests(TestCase):
    def test_turli_shakllar_bitta_raqamga_keladi(self):
        for raw in (
            "+998901234567",
            "998901234567",
            "+998 90 123 45 67",
            "901234567",
            "90 123 45 67",
            "8 90 123 45 67",
            "00998901234567",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(sms.normalize_phone(raw), "998901234567")

    def test_notogri_raqam_bosh_satr(self):
        for raw in ("", None, "12345", "+1 202 555 0143", "salom"):
            with self.subTest(raw=raw):
                self.assertEqual(sms.normalize_phone(raw), "")


class ModeTests(TestCase):
    def test_kredensialsiz_test_rejimi(self):
        with no_sms_env():
            self.assertTrue(sms.is_test_mode())
            self.assertIsInstance(sms.get_provider(), sms.ConsoleSmsProvider)

    def test_kredensial_bilan_haqiqiy_rejim(self):
        with eskiz_env(SMS_DEV_MODE=""):
            self.assertFalse(sms.is_test_mode())
            self.assertIsInstance(sms.get_provider(), sms.EskizSmsProvider)

    def test_dev_mode_bayrogi_ustun(self):
        with eskiz_env(SMS_DEV_MODE="True"):
            self.assertTrue(sms.is_test_mode())

    def test_nomdagi_probel_toqinlik_qilmaydi(self):
        # Railway'da nomni nusxalaganda oxiriga probel tushib qolishi mumkin
        with mock.patch.dict(
            os.environ,
            {"ESKIZ_EMAIL": "", "ESKIZ_EMAIL ": "a@b.uz", "ESKIZ_PASSWORD": "x"},
            clear=False,
        ):
            self.assertEqual(sms._env("ESKIZ_EMAIL"), "a@b.uz")
            self.assertTrue(sms.has_credentials())


class EskizProviderTests(TestCase):
    def setUp(self):
        sms._forget_token()
        self.addCleanup(sms._forget_token)

    def _provider(self):
        with eskiz_env():
            return sms.EskizSmsProvider()

    def test_muvaffaqiyatli_yuborish(self):
        provider = self._provider()
        with mock.patch.object(provider, "_request") as request:
            request.side_effect = [
                (200, {"data": {"token": "tok"}}),
                (200, {"id": "1", "status": "waiting"}),
            ]
            self.assertTrue(provider.send(PHONE, "salom"))

        # Raqam Eskiz kutgan shaklda ketdi
        _path, payload = request.call_args[0][0], request.call_args[0][1]
        self.assertEqual(payload["mobile_phone"], "998901234567")

    def test_token_keshlanadi(self):
        provider = self._provider()
        with mock.patch.object(provider, "_request") as request:
            request.side_effect = [
                (200, {"data": {"token": "tok"}}),
                (200, {"status": "waiting"}),
                (200, {"status": "waiting"}),
            ]
            provider.send(PHONE, "bir")
            provider.send(PHONE, "ikki")
            # 1 ta login + 2 ta xabar (har SMS uchun qayta login qilinmaydi)
            self.assertEqual(request.call_count, 3)

    def test_token_eskirsa_yangilanadi(self):
        provider = self._provider()
        with mock.patch.object(provider, "_request") as request:
            request.side_effect = [
                (200, {"data": {"token": "eski"}}),
                (401, {"message": "Expired token"}),
                (200, {"data": {"token": "yangi"}}),
                (200, {"status": "waiting"}),
            ]
            self.assertTrue(provider.send(PHONE, "salom"))
            self.assertEqual(request.call_count, 4)

    def test_status_error_muvaffaqiyat_deb_hisoblanmaydi(self):
        # Eskiz ba'zan HTTP 200 bilan birga {"status": "error"} qaytaradi
        provider = self._provider()
        with mock.patch.object(provider, "_request") as request:
            request.side_effect = [
                (200, {"data": {"token": "tok"}}),
                (200, {"status": "error", "message": "invalid"}),
            ]
            self.assertFalse(provider.send(PHONE, "salom"))

    def test_shablon_rad_etilsa_muvaffaqiyatsiz(self):
        provider = self._provider()
        with mock.patch.object(provider, "_request") as request:
            request.side_effect = [
                (200, {"data": {"token": "tok"}}),
                (400, {"message": "message is not allowed"}),
            ]
            self.assertFalse(provider.send(PHONE, "tasdiqlanmagan matn"))
            # Zaxira o'chiq — ikkinchi urinish bo'lmaydi
            self.assertEqual(request.call_count, 2)

    def test_shablon_rad_etilsa_test_matni_yuboriladi(self):
        """Hisob "test" rolidagi davr: kod o'rniga bo'lsa ham SMS kelsin."""
        with eskiz_env(ESKIZ_TEST_TEXT_FALLBACK="True"):
            provider = sms.EskizSmsProvider()
            with mock.patch.object(provider, "_request") as request:
                request.side_effect = [
                    (200, {"data": {"token": "tok"}}),
                    (400, {"message": "test rejimida faqat shu matn mumkin"}),
                    (200, {"id": "7", "status": "waiting"}),
                ]
                # Kod yetkazilmagani uchun natija baribir False
                self.assertFalse(provider.send(PHONE, "Savin: kodingiz 123456"))

        # Uchinchi so'rov — aynan Eskiz'ning standart test matni
        payload = request.call_args[0][1]
        self.assertEqual(payload["message"], sms.EskizSmsProvider.ESKIZ_TEST_TEXT)
        self.assertEqual(payload["mobile_phone"], "998901234567")

    def test_raqam_taqiqlangan_bolsa_test_matni_yuborilmaydi(self):
        # "Number is forbidden" — matn emas, raqam muammosi. Ikkinchi urinish
        # ham xuddi shu xato bilan qaytadi, shuning uchun urinilmaydi.
        with eskiz_env(ESKIZ_TEST_TEXT_FALLBACK="True"):
            provider = sms.EskizSmsProvider()
            with mock.patch.object(provider, "_request") as request:
                request.side_effect = [
                    (200, {"data": {"token": "tok"}}),
                    (400, {"message": "Number is forbidden", "status": "error"}),
                ]
                self.assertFalse(provider.send(PHONE, "salom"))
                self.assertEqual(request.call_count, 2)

    def test_login_ishlamasa_yuborilmaydi(self):
        provider = self._provider()
        with mock.patch.object(provider, "_request") as request:
            request.side_effect = [(401, {"message": "Unauthorized"})]
            self.assertFalse(provider.send(PHONE, "salom"))

    def test_notogri_raqamga_sorov_ketmaydi(self):
        provider = self._provider()
        with mock.patch.object(provider, "_request") as request:
            self.assertFalse(provider.send("12345", "salom"))
            request.assert_not_called()

    def test_send_sms_istisno_kotarmaydi(self):
        with eskiz_env(), mock.patch.object(
            sms.EskizSmsProvider, "send", side_effect=RuntimeError("boom")
        ):
            self.assertFalse(sms.send_sms(PHONE, "salom"))


class CredentialsFileTests(TestCase):
    """Vaqtinchalik `sms_credentials.py` fayli orqali sozlash.

    Eskiz tiketi kutilayotgan davrda kredensiallar shu faylda turadi. Eng
    muhim shart: muhit o'zgaruvchisi fayldan USTUN bo'lishi kerak — aks holda
    keyinchalik `.env` ga ko'chirilganda eski qiymatlar yopishib qolardi.
    """

    def test_fayldan_oqiladi(self):
        with mock.patch.dict(os.environ, CLEAN_SMS_ENV, clear=False):
            with mock.patch.object(sms, "_from_file", return_value="fayldan@savin.uz"):
                self.assertEqual(sms._env("ESKIZ_EMAIL"), "fayldan@savin.uz")

    def test_muhit_fayldan_ustun(self):
        with mock.patch.dict(os.environ, {"ESKIZ_EMAIL": "muhitdan@savin.uz"}, clear=False):
            with mock.patch.object(sms, "_from_file", return_value="fayldan@savin.uz"):
                self.assertEqual(sms._env("ESKIZ_EMAIL"), "muhitdan@savin.uz")

    def test_fayl_ochirilsa_yiqilmaydi(self):
        # `sms_credentials.py` o'chirilgan holat (tiketdan keyin shunday bo'ladi)
        with self.settings(TESTING=False):
            with mock.patch.dict("sys.modules", {"mobileapi.sms_credentials": None}):
                self.assertEqual(sms._from_file("ESKIZ_EMAIL"), "")

    def test_testlarda_fayl_oqilmaydi(self):
        # Muhim kafolat: `manage.py test` hech qachon haqiqiy kredensiallar
        # bilan ishlamaydi va Eskiz'ga chinakam so'rov yubormaydi.
        with self.settings(TESTING=True):
            self.assertEqual(sms._from_file("ESKIZ_EMAIL"), "")
            self.assertEqual(sms._from_file("ESKIZ_PASSWORD"), "")

    def test_manba_korsatiladi(self):
        with mock.patch.dict(os.environ, CLEAN_SMS_ENV, clear=False):
            with mock.patch.object(sms, "_from_file", return_value="x@y.uz"):
                self.assertIn("sms_credentials", sms.credentials_source())
        with mock.patch.dict(os.environ, {"ESKIZ_EMAIL": "a@b.uz"}, clear=False):
            self.assertIn("muhit", sms.credentials_source())


class OtpInResponseFallbackTests(TestCase):
    """SMS ketmasa kodni javobda qaytarish — VAQTINCHALIK zaxira yo'l.

    Eskiz hisobi "test" rolida bo'lgani uchun shu davrda ro'yxatdan o'tish
    barcha raqamlar uchun xatosiz ishlashi kerak.
    """

    def setUp(self):
        self.url = reverse("mobile-register")

    def test_sms_ketmasa_kod_javobda_qaytadi(self):
        with eskiz_env(SMS_ALLOW_OTP_IN_RESPONSE="True"), mock.patch.object(
            sms, "send_sms", return_value=False
        ):
            resp = self.client.post(
                self.url, {"first_name": "Ali", "phone_number": PHONE}, "application/json"
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["dev_otp"]), 6)

    def test_qaytgan_kod_bilan_kirish_mumkin(self):
        with eskiz_env(SMS_ALLOW_OTP_IN_RESPONSE="True"), mock.patch.object(
            sms, "send_sms", return_value=False
        ):
            resp = self.client.post(
                self.url, {"first_name": "Ali", "phone_number": PHONE}, "application/json"
            )
        code = resp.json()["dev_otp"]
        resp = self.client.post(
            reverse("mobile-login"),
            {"phone_number": PHONE, "otp_code": code},
            "application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.json())

    def test_sms_ketsa_kod_javobda_qaytmaydi(self):
        # Eskiz shabloni tasdiqlangach zaxira yo'l ishlatilmaydi
        with eskiz_env(SMS_ALLOW_OTP_IN_RESPONSE="True"), mock.patch.object(
            sms, "send_sms", return_value=True
        ):
            resp = self.client.post(
                self.url, {"first_name": "Ali", "phone_number": PHONE}, "application/json"
            )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("dev_otp", resp.json())

    def test_bayroq_ochiq_bolsa_503(self):
        with eskiz_env(), mock.patch.object(sms, "send_sms", return_value=False):
            resp = self.client.post(
                self.url, {"first_name": "Ali", "phone_number": PHONE}, "application/json"
            )
        self.assertEqual(resp.status_code, 503)


class BusinessDecisionSmsTests(TestCase):
    """Landing arizasi tasdiqlanganda/rad etilganda biznes egasiga SMS.

    Zanjir: admin panel -> `core.bridge.notify_main_backend` ->
    `businesses.services.approve_application` -> `send_business_decision_sms`.
    Shu zanjir uzilib qolmasin.
    """

    def setUp(self):
        from businesses.models import Application, Category

        self.category = Category.objects.create(name="Barbershop")
        self.application = Application.objects.create(
            business_name="Sinov Barbershop",
            category=self.category,
            phone_number="+998901234567",
            email="egasi@sinov.uz",
            status=Application.Status.PENDING,
        )

    def test_tasdiqlanganda_sms_ketadi(self):
        from businesses.services import approve_application

        with mock.patch.object(sms, "send_sms", return_value=True) as send:
            approve_application(self.application)

        send.assert_called_once()
        phone, text = send.call_args[0]
        self.assertEqual(phone, "+998901234567")
        self.assertIn("Sinov Barbershop", text)
        self.assertIn("tasdiqlandi", text)

    def test_rad_etilganda_sabab_bilan_sms_ketadi(self):
        from businesses.services import reject_application

        with mock.patch.object(sms, "send_sms", return_value=True) as send:
            reject_application(self.application, reason="Hujjatlar to'liq emas")

        send.assert_called_once()
        _phone, text = send.call_args[0]
        self.assertIn("rad etildi", text)
        self.assertIn("Hujjatlar to'liq emas", text)

    def test_sms_xatosi_tasdiqlashni_toxtatmaydi(self):
        from businesses.services import approve_application

        with mock.patch.object(sms, "send_sms", return_value=False):
            business = approve_application(self.application)

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, self.application.Status.APPROVED)
        self.assertIsNotNone(business)

    def test_telefonsiz_arizada_yiqilmaydi(self):
        from businesses.services import approve_application

        self.application.phone_number = ""
        self.application.save(update_fields=["phone_number"])
        with mock.patch.object(sms, "send_sms") as send:
            approve_application(self.application)
        send.assert_not_called()


class AccountInfoTests(TestCase):
    """`manage.py sms_test` hisob holatini to'g'ri o'qiydimi.

    Aynan shu ma'lumot (rol + tasdiqlangan shablonlar) SMS ketishi yoki
    ketmasligini oldindan aytib beradi.
    """

    def setUp(self):
        sms._forget_token()
        self.addCleanup(sms._forget_token)

    def test_hisob_malumoti_oqiladi(self):
        with eskiz_env(), mock.patch.object(sms.EskizSmsProvider, "_request") as request:
            request.side_effect = [
                (200, {"data": {"token": "tok"}}),
                (
                    200,
                    {
                        "data": {
                            "name": "Firma",
                            "role": "test",
                            "status": "active",
                            "balance": 4650,
                        }
                    },
                ),
                (200, {"result": [{"template": "Kod {code}", "status": "service"}]}),
            ]
            ok, data = sms.account_info()

        self.assertTrue(ok)
        self.assertEqual(data["role"], "test")
        self.assertEqual(data["balance"], 4650)
        self.assertEqual(data["templates"], ["Kod {code}   [service]"])

    def test_shablonlar_bosh_bolsa(self):
        with eskiz_env(), mock.patch.object(sms.EskizSmsProvider, "_request") as request:
            request.side_effect = [
                (200, {"data": {"token": "tok"}}),
                (200, {"data": {"role": "user"}}),
                (200, {"result": []}),
            ]
            ok, data = sms.account_info()

        self.assertTrue(ok)
        self.assertEqual(data["templates"], [])
        self.assertEqual(data["name"], "—")

    def test_login_ishlamasa_xato_qaytadi(self):
        with eskiz_env(), mock.patch.object(sms.EskizSmsProvider, "_request") as request:
            request.side_effect = [(401, {"message": "Unauthorized"})]
            ok, data = sms.account_info()

        self.assertFalse(ok)
        self.assertIn("parol", data)

    def test_kredensialsiz_xato_qaytadi(self):
        with no_sms_env():
            ok, data = sms.account_info()
        self.assertFalse(ok)
        self.assertIn("ESKIZ_EMAIL", data)

    def test_kutilmagan_shakl_yiqilmaydi(self):
        # Eskiz javob shaklini o'zgartirsa ham buyruq ishlashda davom etsin
        self.assertEqual(sms.template_label("oddiy matn"), "oddiy matn")
        self.assertEqual(sms.template_label({"template": "Kod"}), "Kod")


class OtpTests(TestCase):
    def test_kod_yaratiladi_va_tekshiriladi(self):
        with no_sms_env():
            _otp, code, sent = sms.create_and_send(PHONE)
        self.assertTrue(sent)
        self.assertEqual(len(code), 6)
        ok, error = sms.verify(PHONE, code)
        self.assertTrue(ok, error)

    def test_kod_bir_marta_ishlaydi(self):
        with no_sms_env():
            _otp, code, _sent = sms.create_and_send(PHONE)
        self.assertTrue(sms.verify(PHONE, code)[0])
        self.assertFalse(sms.verify(PHONE, code)[0])

    def test_raqam_shakli_farq_qilsa_ham_topiladi(self):
        with no_sms_env():
            _otp, code, _sent = sms.create_and_send("+998901234567")
        ok, error = sms.verify("998901234567", code)
        self.assertTrue(ok, error)

    def test_notogri_kod_urinishlarni_kamaytiradi(self):
        with no_sms_env():
            otp, code, _sent = sms.create_and_send(PHONE)
        ok, error = sms.verify(PHONE, "000000" if code != "000000" else "111111")
        self.assertFalse(ok)
        otp.refresh_from_db()
        self.assertEqual(otp.attempts, 1)
        self.assertIn("urinish", error)

    def test_urinishlar_tugasa_togri_kod_ham_otmaydi(self):
        with no_sms_env():
            otp, code, _sent = sms.create_and_send(PHONE)
        otp.attempts = PhoneOtp.MAX_ATTEMPTS
        otp.save(update_fields=["attempts"])
        self.assertFalse(sms.verify(PHONE, code)[0])

    def test_muddati_tugagan_kod_otmaydi(self):
        with no_sms_env():
            otp, code, _sent = sms.create_and_send(PHONE)
        otp.expires_at = timezone.now() - timedelta(seconds=1)
        otp.save(update_fields=["expires_at"])
        ok, error = sms.verify(PHONE, code)
        self.assertFalse(ok)
        self.assertIn("muddati", error)

    def test_yangi_kod_eskisini_bekor_qiladi(self):
        with no_sms_env():
            _otp1, code1, _ = sms.create_and_send(PHONE)
            _otp2, code2, _ = sms.create_and_send(PHONE)
        self.assertFalse(sms.verify(PHONE, code1)[0])
        self.assertTrue(sms.verify(PHONE, code2)[0])

    def test_qayta_yuborish_oraligi(self):
        self.assertEqual(sms.seconds_until_resend(PHONE), 0)
        with no_sms_env():
            sms.create_and_send(PHONE)
        self.assertGreater(sms.seconds_until_resend(PHONE), 0)

    def test_kod_ochiq_saqlanmaydi(self):
        with no_sms_env():
            otp, code, _sent = sms.create_and_send(PHONE)
        self.assertNotIn(code, otp.code_hash)


class RegisterEndpointTests(TestCase):
    def setUp(self):
        self.url = reverse("mobile-register")

    def test_test_rejimida_kod_javobda_qaytadi(self):
        with no_sms_env():
            resp = self.client.post(
                self.url, {"first_name": "Ali", "phone_number": PHONE}, "application/json"
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["dev_otp"]), 6)
        self.assertTrue(resp.json()["test_mode"])
        self.assertTrue(User.objects.filter(phone_number=PHONE).exists())

    def test_haqiqiy_rejimda_kod_qaytmaydi(self):
        with eskiz_env(), mock.patch.object(sms, "send_sms", return_value=True):
            resp = self.client.post(
                self.url, {"first_name": "Ali", "phone_number": PHONE}, "application/json"
            )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("dev_otp", resp.json())

    def test_sms_ketmasa_503_qaytadi(self):
        # Eng muhim holat: provayder rad etsa foydalanuvchini kelmaydigan
        # SMSni kutib turadigan ekranga o'tkazmaymiz.
        with eskiz_env(), mock.patch.object(sms, "send_sms", return_value=False):
            resp = self.client.post(
                self.url, {"first_name": "Ali", "phone_number": PHONE}, "application/json"
            )
        self.assertEqual(resp.status_code, 503)
        self.assertTrue(resp.json()["sms_failed"])

    def test_tez_qayta_sorash_429(self):
        with no_sms_env():
            self.client.post(
                self.url, {"first_name": "Ali", "phone_number": PHONE}, "application/json"
            )
            resp = self.client.post(
                self.url, {"first_name": "Ali", "phone_number": PHONE}, "application/json"
            )
        self.assertEqual(resp.status_code, 429)
        self.assertGreater(resp.json()["retry_after"], 0)

    def test_telefonsiz_sorov_400(self):
        resp = self.client.post(self.url, {"first_name": "Ali"}, "application/json")
        self.assertEqual(resp.status_code, 400)


class LoginEndpointTests(TestCase):
    def setUp(self):
        self.register_url = reverse("mobile-register")
        self.login_url = reverse("mobile-login")

    def _register(self):
        with no_sms_env():
            resp = self.client.post(
                self.register_url,
                {"first_name": "Ali", "phone_number": PHONE},
                "application/json",
            )
        return resp.json()["dev_otp"]

    def test_togri_kod_bilan_kirish(self):
        code = self._register()
        resp = self.client.post(
            self.login_url,
            {"phone_number": PHONE, "otp_code": code},
            "application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.json())

    def test_kodsiz_kirib_bolmaydi(self):
        self._register()
        resp = self.client.post(
            self.login_url, {"phone_number": PHONE, "otp_code": ""}, "application/json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_notogri_kod_rad_etiladi(self):
        code = self._register()
        wrong = "000000" if code != "000000" else "111111"
        resp = self.client.post(
            self.login_url,
            {"phone_number": PHONE, "otp_code": wrong},
            "application/json",
        )
        self.assertEqual(resp.status_code, 400)


class SmsStatusEndpointTests(TestCase):
    def setUp(self):
        self.url = reverse("mobile-sms-status")

    def test_debug_rejimida_ochiq(self):
        with self.settings(DEBUG=True):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("test_mode", resp.json())

    def test_production_da_tokensiz_yopiq(self):
        with self.settings(DEBUG=False), mock.patch.dict(
            os.environ, {"SMS_STATUS_TOKEN": ""}, clear=False
        ):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_production_da_token_bilan_ochiq(self):
        with self.settings(DEBUG=False), mock.patch.dict(
            os.environ, {"SMS_STATUS_TOKEN": "maxfiy"}, clear=False
        ):
            resp = self.client.get(self.url, {"token": "maxfiy"})
        self.assertEqual(resp.status_code, 200)

    def test_javobda_maxfiy_qiymat_yoq(self):
        with self.settings(DEBUG=True), eskiz_env():
            resp = self.client.get(self.url)
        body = resp.content.decode()
        self.assertNotIn("secret", body)
        self.assertNotIn("test@savin.uz", body)


class RedeemCodeTests(TestCase):
    """QR o'rniga aytiladigan 4 xonali kod."""

    def setUp(self):
        self.url = reverse("mobile-redeem-code")
        self.user = User.objects.create_user(
            username="c@customer.savin.local",
            email="c@customer.savin.local",
            password="pass12345",
            phone_number=PHONE,
            role=User.Role.CUSTOMER,
        )

    def _auth(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(self.user).access_token
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    def test_kod_4_xonali_va_barqaror(self):
        self._auth()
        r1 = self.client.get(self.url)
        self.assertEqual(r1.status_code, 200)
        code = r1.json()["code"]
        self.assertRegex(code, r"^\d{4}$")
        # Muddati tugamaguncha o'sha kod qaytadi
        r2 = self.client.get(self.url)
        self.assertEqual(r2.json()["code"], code)

    def test_kod_yangilanadi(self):
        from mobileapi.models import RedeemCode
        from mobileapi.views import get_or_refresh_redeem_code

        rc = get_or_refresh_redeem_code(self.user)
        old = rc.code
        # Muddatini o'tkazamiz
        rc.expires_at = timezone.now() - timedelta(seconds=1)
        rc.save(update_fields=["expires_at"])
        rc2 = get_or_refresh_redeem_code(self.user)
        self.assertGreater(rc2.expires_at, timezone.now())
        # Bitta foydalanuvchida bitta yozuv
        self.assertEqual(RedeemCode.objects.filter(user=self.user).count(), 1)
        _ = old  # kod bir xil ham chiqishi mumkin — muhimi muddat yangilandi

    def test_kassir_kod_orqali_mijozni_topadi(self):
        from discounts.views import find_customer_by_qr
        from mobileapi.views import get_or_refresh_redeem_code

        rc = get_or_refresh_redeem_code(self.user)
        found, err = find_customer_by_qr(rc.code)
        self.assertIsNone(err)
        self.assertEqual(found, self.user)

    def test_muddati_tugagan_kod_topilmaydi(self):
        from discounts.views import find_customer_by_qr
        from mobileapi.models import RedeemCode

        RedeemCode.objects.create(
            user=self.user, code="1234",
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        found, err = find_customer_by_qr("1234")
        self.assertIsNone(found)
        self.assertIn("muddati", err)


class TwoFactorLoginTests(TestCase):
    """Panel logini: 2FA yoqilgan bo'lsa kod HAQIQATDA tekshiriladi."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="owner",
            email="owner@biznes.uz",
            password="owner12345",
            phone_number=PHONE,
        )
        self.user.is_2fa_enabled = True
        self.user.save(update_fields=["is_2fa_enabled"])

    def _login(self, otp_code=None):
        from users.serializers import LoginSerializer

        data = {"email": "owner@biznes.uz", "password": "owner12345"}
        if otp_code is not None:
            data["otp_code"] = otp_code
        return LoginSerializer(data=data)

    def test_kodsiz_kirish_rad_etiladi_va_kod_yuboriladi(self):
        with no_sms_env():
            self.assertFalse(self._login().is_valid())
        self.assertTrue(PhoneOtp.objects.filter(phone="998901234567").exists())

    def test_ixtiyoriy_kod_otmaydi(self):
        with no_sms_env():
            sms.create_and_send(PHONE)
            self.assertFalse(self._login("000000").is_valid())

    def test_togri_kod_otadi(self):
        with no_sms_env():
            _otp, code, _sent = sms.create_and_send(PHONE)
            serializer = self._login(code)
            self.assertTrue(serializer.is_valid(), serializer.errors)
