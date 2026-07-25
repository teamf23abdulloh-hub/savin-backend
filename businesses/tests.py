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
