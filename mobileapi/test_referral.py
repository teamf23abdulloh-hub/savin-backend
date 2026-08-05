"""Referal oqimi va kassir chegirmasining mijoz ilovasida ko'rinishi.

Qamrab olinadi:
  * taklif kodi orqali do'stni biriktirish (deep-link oqimining backend qismi),
  * do'st bir hafta ilovaga kirsa "Aktiv" bo'lishi va qolgan kunlar,
  * 3 ta faol do'stdan keyingina obuna arizasi yuborilishi,
  * admin tasdiqlaganda a'zolik +1 oyga uzayishi,
  * kassir qo'llagan chegirma mijozning "tejagan summasi"da ko'rinishi.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from businesses.models import Business, BusinessType, Category
from mobileapi.models import ReferralInvite, ReferralRequest
from mobileapi.services import (
    ReferralError,
    attach_referral,
    create_reward_request,
    get_referral_code,
    record_activity,
    referral_overview,
    review_referral_request,
)
from transactions.models import Transaction
from users.models import Membership, User


def make_customer(suffix, first_name="Aziz"):
    return User.objects.create_user(
        username=f"user{suffix}",
        email=f"user{suffix}@customer.savin.local",
        password="x",
        role=User.Role.CUSTOMER,
        phone_number=f"+99890123{suffix:04d}",
        first_name=first_name,
    )


class ReferralFlowTests(TestCase):
    def setUp(self):
        self.inviter = make_customer(1, "Aziz")
        self.client = APIClient()

    def test_code_is_stable_and_name_based(self):
        code = get_referral_code(self.inviter).code
        self.assertTrue(code.startswith("AZIZ"), code)
        self.assertEqual(get_referral_code(self.inviter).code, code)

    def test_attach_referral_links_friend(self):
        code = get_referral_code(self.inviter).code
        friend = make_customer(2, "Jasur")

        invite = attach_referral(friend, code)

        self.assertIsNotNone(invite)
        self.assertEqual(invite.inviter, self.inviter)
        self.assertEqual(invite.status, ReferralInvite.Status.PENDING)
        self.assertEqual(invite.days_left, ReferralInvite.ACTIVE_DAYS_REQUIRED)

    def test_cannot_invite_self_or_twice(self):
        code = get_referral_code(self.inviter).code
        self.assertIsNone(attach_referral(self.inviter, code))

        friend = make_customer(3)
        self.assertIsNotNone(attach_referral(friend, code))
        # Ikkinchi marta biriktirilmaydi
        other = make_customer(4, "Ulugbek")
        self.assertIsNone(attach_referral(friend, get_referral_code(other).code))

    def test_registration_attaches_referral_code(self):
        code = get_referral_code(self.inviter).code
        res = self.client.post(
            "/api/v1/mobile/auth/register/",
            {
                "first_name": "Diyora",
                "phone_number": "+998911112233",
                "referral_code": code.lower(),  # katta-kichik harf muhim emas
            },
            format="json",
        )
        self.assertIn(res.status_code, (200, 503))
        friend = User.objects.get(phone_number="+998911112233")
        self.assertTrue(ReferralInvite.objects.filter(invitee=friend).exists())

    def test_seven_days_of_activity_activates_invite(self):
        friend = make_customer(5, "Jasur")
        invite = attach_referral(friend, get_referral_code(self.inviter).code)

        # Bir kunda bir necha marta kirish — bitta kun hisoblanadi
        record_activity(friend)
        record_activity(friend)
        invite.refresh_from_db()
        self.assertEqual(invite.active_days, 1)
        self.assertEqual(invite.days_left, 6)
        self.assertEqual(invite.status, ReferralInvite.Status.PENDING)

        # Qolgan kunlarni "kecha kirgan" holatiga qo'yib yig'amiz
        for day in range(2, ReferralInvite.ACTIVE_DAYS_REQUIRED + 1):
            invite.last_active_date = timezone.localdate() - timedelta(days=1)
            invite.save(update_fields=["last_active_date"])
            record_activity(friend)
            invite.refresh_from_db()
            self.assertEqual(invite.active_days, day)

        self.assertEqual(invite.status, ReferralInvite.Status.ACTIVE)
        self.assertEqual(invite.days_left, 0)
        self.assertIsNotNone(invite.activated_at)

    def _activate(self, friend):
        invite = ReferralInvite.objects.get(invitee=friend)
        invite.active_days = ReferralInvite.ACTIVE_DAYS_REQUIRED
        invite.status = ReferralInvite.Status.ACTIVE
        invite.activated_at = timezone.now()
        invite.save()
        return invite

    def test_reward_request_needs_three_active_friends(self):
        code = get_referral_code(self.inviter).code
        friends = [make_customer(10 + i) for i in range(3)]
        for f in friends:
            attach_referral(f, code)

        # Hali hech kim faollashmagan
        with self.assertRaises(ReferralError):
            create_reward_request(self.inviter)

        self._activate(friends[0])
        self._activate(friends[1])
        overview = referral_overview(self.inviter)
        self.assertEqual(overview["active_count"], 2)
        self.assertEqual(overview["remaining_for_reward"], 1)
        self.assertFalse(overview["can_request"])

        self._activate(friends[2])
        req = create_reward_request(self.inviter)
        self.assertEqual(req.status, ReferralRequest.Status.PENDING)
        self.assertEqual(
            ReferralInvite.objects.filter(reward_request=req).count(), 3
        )

        # Ikkinchi ariza — do'stlar allaqachon band
        with self.assertRaises(ReferralError):
            create_reward_request(self.inviter)

    def test_approval_extends_membership_by_one_month(self):
        code = get_referral_code(self.inviter).code
        for i in range(3):
            f = make_customer(20 + i)
            attach_referral(f, code)
            self._activate(f)
        req = create_reward_request(self.inviter)

        review_referral_request(str(req.id), "approve")

        membership = Membership.objects.get(user=self.inviter)
        self.assertEqual(membership.status, Membership.Status.ACTIVE)
        self.assertGreater(
            membership.expires_at, timezone.now() + timedelta(days=29)
        )

    def test_rejection_frees_friends_for_a_new_request(self):
        code = get_referral_code(self.inviter).code
        for i in range(3):
            f = make_customer(30 + i)
            attach_referral(f, code)
            self._activate(f)
        req = create_reward_request(self.inviter)

        review_referral_request(str(req.id), "reject", "Shubhali hisoblar")

        self.assertEqual(
            ReferralInvite.objects.filter(reward_request__isnull=True).count(), 3
        )
        # Qayta ariza yuborish mumkin
        self.assertIsNotNone(create_reward_request(self.inviter))

    def test_overview_endpoint_returns_friend_progress(self):
        friend = make_customer(40, "Jasur")
        attach_referral(friend, get_referral_code(self.inviter).code)
        record_activity(friend)

        self.client.force_authenticate(user=self.inviter)
        res = self.client.get("/api/v1/mobile/referral/overview/")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["invited_count"], 1)
        self.assertEqual(res.data["active_count"], 0)
        self.assertIn("/i/", res.data["link"])
        self.assertEqual(res.data["friends"][0]["days_left"], 6)

    def test_activity_ping_endpoint(self):
        friend = make_customer(41)
        attach_referral(friend, get_referral_code(self.inviter).code)

        self.client.force_authenticate(user=friend)
        res = self.client.post("/api/v1/mobile/activity/ping/")

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["invited"])
        self.assertEqual(res.data["active_days"], 1)
        self.assertEqual(res.data["days_left"], 6)


class CashierDiscountVisibleToCustomerTests(TestCase):
    """Kassir chegirma qo'llasa — mijoz ilovasida tejagan summa ko'rinsin."""

    def setUp(self):
        self.customer = make_customer(50)
        owner = User.objects.create_user(
            username="owner",
            email="owner@savin.local",
            password="x",
            role=User.Role.BUSINESS_OWNER,
        )
        category = Category.objects.create(name="Barber", slug="barber")
        self.business = Business.objects.create(
            name="Fresh Cut Barber",
            owner=owner,
            category=category,
            business_type=BusinessType.YATT,
            phone_number="+998901112233",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.customer)

    def _tx(self, **kwargs):
        return Transaction.objects.create(
            business=self.business,
            service_name="Soch olish",
            base_price=100000,
            discount_percent=20,
            status="completed",
            **kwargs,
        )

    def test_transaction_linked_by_customer_account(self):
        self._tx(customer=self.customer, customer_name="Aziz")

        res = self.client.get("/api/v1/mobile/transactions/stats/")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["saved_all_time"], 20000)
        self.assertEqual(res.data["visits"], 1)

    def test_transaction_matched_by_phone_in_any_format(self):
        # Kassir raqamni boshqacha formatda yozgan bo'lsa ham topilsin
        digits = self.customer.phone_number.replace("+", "")
        self._tx(customer_name="Aziz", customer_phone=digits)

        res = self.client.get("/api/v1/mobile/transactions/")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["saved_amount"], 20000)

    def test_customer_gets_notification_about_discount(self):
        self._tx(customer=self.customer, customer_name="Aziz")

        res = self.client.get("/api/v1/mobile/notifications/")

        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            any("Chegirma qo'llanildi" in n["title"] for n in res.data), res.data
        )
