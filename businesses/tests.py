from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from businesses.models import Application, Category
from notifications.models import UserNotification

User = get_user_model()


class ApplicationWizardTestCase(APITestCase):
    """Landing'dan ariza qoldirish (4 qadamli wizard) oqimi testlari."""

    def setUp(self):
        self.category = Category.objects.create(name="Go'zallik", slug="gozallik")
        self.admin = User.objects.create_user(
            username="admin@savin.uz",
            email="admin@savin.uz",
            password="adminpass123",
            role="admin",
        )
        self.client = APIClient()

    def _create_step1(self):
        return self.client.post(
            "/api/v1/applications/step1/",
            {
                "business_name": "Barbershop Lux",
                "category": str(self.category.id),
                "business_type": "yatt",
                "responsible_full_name": "Aziz Karimov",
                "short_description": "Soch olish xizmatlari",
            },
            format="json",
        )

    def test_full_wizard_creates_pending_application_and_notifies_admin(self):
        """4 qadam to'ldirilgach ariza PENDING bo'ladi va adminga bildirishnoma boradi."""
        r1 = self._create_step1()
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        app_id = r1.data["id"]

        r2 = self.client.patch(
            f"/api/v1/applications/{app_id}/step/2/",
            {"phone_number": "+998901234567", "email": "biz@test.uz"},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)

        r3 = self.client.patch(
            f"/api/v1/applications/{app_id}/step/3/",
            {
                "region": "tashkent_city",
                "city_district": "Yunusobod",
                "full_address": "Amir Temur ko'chasi, 10",
                "work_days": "everyday",
            },
            format="json",
        )
        self.assertEqual(r3.status_code, status.HTTP_200_OK)

        r4 = self.client.patch(
            f"/api/v1/applications/{app_id}/step/4/",
            {"discount_percent": 15, "discount_type": "fixed"},
            format="json",
        )
        self.assertEqual(r4.status_code, status.HTTP_200_OK)

        application = Application.objects.get(pk=app_id)
        self.assertEqual(application.status, Application.Status.PENDING)

        # Admin panelda bildirishnoma ko'rinishi kerak
        notif = UserNotification.objects.filter(user=self.admin, title="Yangi ariza")
        self.assertEqual(notif.count(), 1)
        self.assertIn("Barbershop Lux", notif.first().body)

        # Arizalar bo'limida (admin ro'yxatida) ko'rinishi kerak
        self.client.force_authenticate(user=self.admin)
        r_list = self.client.get("/api/v1/admin/applications/?status=pending")
        self.assertEqual(r_list.status_code, status.HTTP_200_OK)
        results = r_list.data.get("results", r_list.data)
        self.assertTrue(any(item["id"] == app_id for item in results))

    def test_admin_approve_creates_business(self):
        """Admin tasdiqlasa Business yaratiladi."""
        r1 = self._create_step1()
        app_id = r1.data["id"]
        self.client.patch(
            f"/api/v1/applications/{app_id}/step/2/",
            {"phone_number": "+998901234567"},
            format="json",
        )
        self.client.patch(
            f"/api/v1/applications/{app_id}/step/3/",
            {
                "region": "tashkent_city",
                "city_district": "Yunusobod",
                "full_address": "Amir Temur ko'chasi, 10",
            },
            format="json",
        )
        self.client.patch(
            f"/api/v1/applications/{app_id}/step/4/",
            {"discount_percent": 15},
            format="json",
        )

        # Arizaga applicant biriktiramiz (anonim arizada owner bo'lmaydi,
        # admin tasdiqlashda owner kerak)
        owner = User.objects.create_user(
            username="owner@test.uz",
            email="owner@test.uz",
            password="ownerpass123",
        )
        Application.objects.filter(pk=app_id).update(applicant=owner)

        self.client.force_authenticate(user=self.admin)
        r = self.client.post(
            f"/api/v1/admin/applications/{app_id}/review/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        application = Application.objects.get(pk=app_id)
        self.assertEqual(application.status, Application.Status.APPROVED)
        self.assertIsNotNone(getattr(application, "business", None))
        owner.refresh_from_db()
        self.assertEqual(owner.role, User.Role.BUSINESS_OWNER)

    def test_admin_approve_anonymous_application(self):
        """Anonim (landing) arizani tasdiqlashda email orqali owner yaratiladi."""
        r1 = self._create_step1()
        app_id = r1.data["id"]
        self.client.patch(
            f"/api/v1/applications/{app_id}/step/2/",
            {"phone_number": "+998901234567", "email": "yangi@biznes.uz"},
            format="json",
        )
        self.client.patch(
            f"/api/v1/applications/{app_id}/step/3/",
            {
                "region": "tashkent_city",
                "city_district": "Yunusobod",
                "full_address": "Amir Temur ko'chasi, 10",
            },
            format="json",
        )
        self.client.patch(
            f"/api/v1/applications/{app_id}/step/4/",
            {"discount_percent": 15},
            format="json",
        )

        self.client.force_authenticate(user=self.admin)
        r = self.client.post(
            f"/api/v1/admin/applications/{app_id}/review/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        application = Application.objects.get(pk=app_id)
        self.assertEqual(application.status, Application.Status.APPROVED)
        self.assertIsNotNone(application.applicant)
        self.assertEqual(application.applicant.email, "yangi@biznes.uz")
        self.assertEqual(application.applicant.role, User.Role.BUSINESS_OWNER)


class ProfileChangeApprovalTests(APITestCase):
    """Profil o'zgarishi to'g'ridan saqlanmaydi — admin tasdiqlaydi."""

    def setUp(self):
        self.category = Category.objects.create(name="Kafe2", slug="kafe2")
        self.owner = User.objects.create_user(
            username="own2@savin.uz", email="own2@savin.uz",
            password="pass12345", role=User.Role.BUSINESS_OWNER,
        )
        self.application = Application.objects.create(
            business_name="Old Nom", category=self.category, discount_percent=10,
        )
        from businesses.models import Business
        self.business = Business.objects.create(
            owner=self.owner, application=self.application, name="Old Nom",
            category=self.category, phone_number="+998901112233", is_active=True,
        )
        self.client.force_authenticate(self.owner)

    def test_patch_togridan_saqlanmaydi_sorov_boradi(self):
        resp = self.client.patch(
            "/api/v1/my-business/", {"name": "Yangi Nom"}, format="json",
        )
        self.assertEqual(resp.status_code, 202)
        self.assertTrue(resp.json()["pending"])
        self.business.refresh_from_db()
        self.assertEqual(self.business.name, "Old Nom")  # o'zgarmadi
        from businesses.models import ProfileChangeRequest
        cr = ProfileChangeRequest.objects.get(business=self.business)
        self.assertEqual(cr.changes["name"], "Yangi Nom")

    def test_tasdiqlangach_qollanadi(self):
        self.client.patch(
            "/api/v1/my-business/",
            {"name": "Yangi Nom", "work_hours_from": "09:00", "work_hours_to": "21:00"},
            format="json",
        )
        from businesses.models import ProfileChangeRequest
        from businesses.services import apply_profile_review
        cr = ProfileChangeRequest.objects.get(business=self.business)
        apply_profile_review(cr, "approve")

        self.business.refresh_from_db()
        self.application.refresh_from_db()
        self.assertEqual(self.business.name, "Yangi Nom")
        self.assertEqual(self.application.work_hours_from.strftime("%H:%M"), "09:00")
        self.assertEqual(self.application.work_hours_to.strftime("%H:%M"), "21:00")

    def test_ozgarish_yoq_bolsa_sorov_yaratilmaydi(self):
        resp = self.client.patch(
            "/api/v1/my-business/", {"name": "Old Nom"}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["pending"])
        from businesses.models import ProfileChangeRequest
        self.assertEqual(ProfileChangeRequest.objects.count(), 0)


class CashierLoginUniquenessTests(APITestCase):
    """Kassir login BUTUN tizim bo'ylab noyob — boshqa biznes kassiri bilan
    bir xil bo'lib qolmasligi kerak; jonli tekshiruv ham ishlashi kerak."""

    def setUp(self):
        from businesses.models import Business
        self.cat = Category.objects.create(name="Kafe3", slug="kafe3")
        self.owner_a = User.objects.create_user(
            username="a@savin.uz", email="a@savin.uz", password="pass12345",
            role=User.Role.BUSINESS_OWNER,
        )
        self.owner_b = User.objects.create_user(
            username="b@savin.uz", email="b@savin.uz", password="pass12345",
            role=User.Role.BUSINESS_OWNER,
        )
        self.biz_a = Business.objects.create(owner=self.owner_a, name="A", category=self.cat, is_active=True)
        self.biz_b = Business.objects.create(owner=self.owner_b, name="B", category=self.cat, is_active=True)

    def _create_cashier(self, owner, login):
        self.client.force_authenticate(owner)
        return self.client.post(
            "/api/v1/my-business/cashiers/",
            {"full_name": "Kassir", "login": login, "password": "pass12345"},
            format="json",
        )

    def test_boshqa_biznesda_bir_xil_login_rad_etiladi(self):
        r1 = self._create_cashier(self.owner_a, "baxtiyor")
        self.assertEqual(r1.status_code, 201)
        # Boshqa biznes egasi xuddi shu loginni yaratmoqchi
        r2 = self._create_cashier(self.owner_b, "baxtiyor")
        self.assertEqual(r2.status_code, 400)
        self.assertIn("login", r2.json())
        self.assertIn("mavjud", str(r2.json()["login"]).lower())

    def test_check_login_endpoint(self):
        self._create_cashier(self.owner_a, "baxtiyor")
        self.client.force_authenticate(self.owner_b)
        # Band login
        r = self.client.get("/api/v1/my-business/cashiers/check-login/", {"login": "baxtiyor"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["available"])
        self.assertEqual(r.json()["login"], "baxtiyor@savin.uz")
        # Bo'sh login
        r2 = self.client.get("/api/v1/my-business/cashiers/check-login/", {"login": "yangi"})
        self.assertTrue(r2.json()["available"])
