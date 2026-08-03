"""Chegirma kartasi so'rovi -> admin tasdiqlashi oqimi testlari.

Yangi qoida: biznes egasi chegirma qo'shsa/tahrirlasa u TO'G'RIDAN saqlanmaydi
— avval `DiscountChangeRequest` yaratiladi, admin tasdiqlagach `Discount`
modeliga qo'llanadi.
"""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from businesses.models import Application, Business, Category
from discounts.models import Discount, DiscountChangeRequest
from discounts.views import apply_discount_review

User = get_user_model()


class DiscountCardApprovalTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Kafe", slug="kafe")
        self.owner = User.objects.create_user(
            username="owner@savin.uz",
            email="owner@savin.uz",
            password="ownerpass123",
            role=User.Role.BUSINESS_OWNER,
        )
        self.application = Application.objects.create(
            business_name="BBQ",
            category=self.category,
            discount_percent=15,
        )
        self.business = Business.objects.create(
            owner=self.owner,
            application=self.application,
            name="BBQ",
            category=self.category,
            is_active=True,
        )
        self.client.force_authenticate(self.owner)

    # -- Yaratish --------------------------------------------------------

    def test_yaratish_togridan_saqlanmaydi_sorov_boradi(self):
        resp = self.client.post(
            "/api/v1/my-business/discounts/",
            {"category": "Premium", "percent": 20, "min_purchase": 50000, "is_active": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 202)
        self.assertTrue(resp.json()["pending"])
        self.assertFalse(
            Discount.objects.filter(business=self.business, category="Premium").exists()
        )
        cr = DiscountChangeRequest.objects.get(business=self.business)
        self.assertEqual(cr.action, DiscountChangeRequest.Action.CREATE)
        self.assertEqual(cr.new_percent, 20)

    def test_admin_tasdiqlagach_karta_paydo_boladi(self):
        self.client.post(
            "/api/v1/my-business/discounts/",
            {"category": "Premium", "percent": 20, "is_active": True},
            format="json",
        )
        cr = DiscountChangeRequest.objects.get(business=self.business)
        apply_discount_review(cr, "approve")
        cr.refresh_from_db()

        self.assertEqual(cr.status, DiscountChangeRequest.Status.APPROVED)
        d = Discount.objects.get(business=self.business, category="Premium")
        self.assertEqual(d.percent, 20)
        self.assertTrue(d.is_active)

    def test_admin_rad_etsa_karta_yaratilmaydi(self):
        self.client.post(
            "/api/v1/my-business/discounts/",
            {"category": "VIP", "percent": 30, "is_active": True},
            format="json",
        )
        cr = DiscountChangeRequest.objects.get(business=self.business)
        apply_discount_review(cr, "reject", reject_reason="Juda yuqori")
        cr.refresh_from_db()

        self.assertEqual(cr.status, DiscountChangeRequest.Status.REJECTED)
        self.assertFalse(
            Discount.objects.filter(business=self.business, category="VIP").exists()
        )

    # -- Tahrirlash ------------------------------------------------------

    def test_tahrirlash_togridan_ozgarmaydi(self):
        d = Discount.objects.create(
            business=self.business, category="Premium", percent=20, is_active=True
        )
        resp = self.client.patch(
            f"/api/v1/my-business/discounts/{d.id}/",
            {"percent": 35},
            format="json",
        )
        self.assertEqual(resp.status_code, 202)
        d.refresh_from_db()
        self.assertEqual(d.percent, 20)  # o'zgarmadi
        cr = DiscountChangeRequest.objects.get(business=self.business, action="update")
        self.assertEqual(cr.new_percent, 35)
        self.assertEqual(cr.discount_id, d.id)

    def test_tahrirlash_tasdiqlangach_ozgaradi(self):
        d = Discount.objects.create(
            business=self.business, category="Premium", percent=20, is_active=True
        )
        self.client.patch(
            f"/api/v1/my-business/discounts/{d.id}/",
            {"percent": 35, "description": "Yangi", "is_active": False},
            format="json",
        )
        cr = DiscountChangeRequest.objects.get(action="update")
        apply_discount_review(cr, "approve")
        d.refresh_from_db()
        self.assertEqual(d.percent, 35)
        self.assertEqual(d.description, "Yangi")
        self.assertFalse(d.is_active)

    # -- O'chirish bevosita ishlaydi ------------------------------------

    def test_ochirish_bevosita(self):
        d = Discount.objects.create(
            business=self.business, category="Premium", percent=20, is_active=True
        )
        resp = self.client.delete(f"/api/v1/my-business/discounts/{d.id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Discount.objects.filter(pk=d.id).exists())


class LandingDiscountAsCardTests(APITestCase):
    """Ariza tasdiqlanganda foiz Standart chegirma kartasi bo'lib chiqadi."""

    def test_ariza_tasdiqlansa_standart_karta_yaratiladi(self):
        from businesses.services import approve_application

        category = Category.objects.create(name="Restoran", slug="restoran")
        owner = User.objects.create_user(
            username="rest@savin.uz", email="rest@savin.uz", password="pass12345"
        )
        application = Application.objects.create(
            business_name="Osh Markazi",
            category=category,
            applicant=owner,
            discount_percent=12,
            phone_number="+998901234567",
        )
        business = approve_application(application)

        d = Discount.objects.get(business=business, category=Discount.Category.STANDARD)
        self.assertEqual(d.percent, 12)
        self.assertTrue(d.is_active)
