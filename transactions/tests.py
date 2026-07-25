from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from businesses.models import Business, Cashier, Category

from .models import Transaction, TransactionLog

User = get_user_model()


class TransactionTestCase(APITestCase):
    """Tranzaksiya API testlari"""

    def setUp(self):
        """Test data yaratish"""
        # Category (haqiqiy modelda name + slug bor)
        self.category = Category.objects.create(name="Xizmat", slug="xizmat")

        # Admin user
        self.admin = User.objects.create_user(
            username="admin@test.com",
            email="admin@test.com",
            password="testpass123",
            role="admin",
        )

        # Business owner
        self.business_owner = User.objects.create_user(
            username="owner@test.com",
            email="owner@test.com",
            password="testpass123",
            role="business_owner",
        )

        # Business (haqiqiy model maydonlari bilan)
        self.business = Business.objects.create(
            owner=self.business_owner,
            name="Test Biznes",
            category=self.category,
            business_type="yatt",
            phone_number="+998901112233",
            region="tashkent_city",
            city_district="Chilonzor",
            full_address="Test ko'chasi, 1-uy",
        )

        # Cashier: alohida User + Cashier profili
        self.cashier = User.objects.create_user(
            username="cashier@test.com",
            email="cashier@test.com",
            password="testpass123",
            role="cashier",
        )
        self.cashier_profile = Cashier.objects.create(
            business=self.business,
            user=self.cashier,
            full_name="Kassir User",
        )

        self.client = APIClient()

    def test_cashier_create_transaction(self):
        """Kassir tranzaksiya yaratishi"""
        self.client.force_authenticate(user=self.cashier)

        data = {
            "customer_name": "Aziz Karimov",
            "customer_phone": "+998911234567",
            "service_name": "Soch olish",
            "service_category": "Soch olish",
            "base_price": "50000",
            "discount_percent": 35,
            "notes": "VIP mijoz",
        }

        response = self.client.post("/api/v1/transactions/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Decimal(response.data["final_price"]),
            Decimal("32500"),  # 50000 - 35% = 32500
        )

    def test_transaction_summary(self):
        """Tranzaksiya xulosa"""
        for i in range(3):
            Transaction.objects.create(
                business=self.business,
                cashier=self.cashier,
                customer_name=f"Mijoz {i}",
                service_name="Xizmat",
                base_price=Decimal("100000"),
                discount_percent=20,
            )

        self.client.force_authenticate(user=self.business_owner)
        response = self.client.get("/api/v1/transactions/summary/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_transactions"], 3)
        self.assertEqual(Decimal(response.data["total_final"]), Decimal("240000"))

    def test_transaction_export(self):
        """CSV export"""
        Transaction.objects.create(
            business=self.business,
            cashier=self.cashier,
            customer_name="Test Mijoz",
            service_name="Test Xizmat",
            base_price=Decimal("50000"),
            discount_percent=25,
        )

        self.client.force_authenticate(user=self.business_owner)
        response = self.client.get("/api/v1/transactions/export/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_cancel_transaction(self):
        """Tranzaksiyani bekor qilish"""
        transaction = Transaction.objects.create(
            business=self.business,
            cashier=self.cashier,
            customer_name="Test Mijoz",
            service_name="Test Xizmat",
            base_price=Decimal("50000"),
            discount_percent=0,
        )

        self.client.force_authenticate(user=self.cashier)
        response = self.client.post(f"/api/v1/transactions/{transaction.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, "cancelled")

    def test_refund_transaction(self):
        """Tranzaksiyada refund"""
        transaction = Transaction.objects.create(
            business=self.business,
            cashier=self.cashier,
            customer_name="Test Mijoz",
            service_name="Test Xizmat",
            base_price=Decimal("50000"),
            discount_percent=0,
        )

        self.client.force_authenticate(user=self.cashier)
        response = self.client.post(f"/api/v1/transactions/{transaction.id}/refund/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, "refunded")

    def test_transaction_log_created(self):
        """Tranzaksiya log yaratilishi"""
        self.client.force_authenticate(user=self.cashier)

        data = {
            "customer_name": "Test Mijoz",
            "service_name": "Test Xizmat",
            "base_price": "50000",
            "discount_percent": 10,
        }

        response = self.client.post("/api/v1/transactions/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        transaction_id = response.data["id"]
        logs = TransactionLog.objects.filter(transaction_id=transaction_id)

        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().action, "created")

    def test_permission_non_cashier_cannot_create(self):
        """Kassir emas tranzaksiya yarat olmaydi"""
        self.client.force_authenticate(user=self.business_owner)

        data = {
            "customer_name": "Test Mijoz",
            "service_name": "Test Xizmat",
            "base_price": "50000",
            "discount_percent": 10,
        }

        response = self.client.post("/api/v1/transactions/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
