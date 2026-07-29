"""To'lovni boshlash va provayder webhook'lari (Payme, Click).

Oqim:
1. Ilova `POST /payments/create/` chaqiradi -> `Payment` (pending) yaratiladi
   va `checkout_url` qaytadi.
2. Foydalanuvchi o'sha havolada to'laydi.
3. Provayder webhook yuboradi -> to'lov `success` bo'ladi va a'zolik
   faollashadi.

Test rejimida (kredensiallar yo'q) 2-qadam bizning `/payments/test/<id>/`
sahifamiz orqali bajariladi — oqimni to'liq sinash mumkin.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payments import gateways
from payments.models import Payment
from users.models import Membership

logger = logging.getLogger(__name__)

# A'zolik narxi va muddati (so'm / kun)
MEMBERSHIP_PRICE = Decimal(gateways._env("MEMBERSHIP_PRICE", "50000"))
MEMBERSHIP_DAYS = int(gateways._env("MEMBERSHIP_DAYS", "30"))


def activate_membership(user, days=MEMBERSHIP_DAYS):
    """To'lov muvaffaqiyatli bo'lganda a'zolikni faollashtiradi/uzaytiradi."""
    now = timezone.now()
    membership, _ = Membership.objects.get_or_create(user=user)
    # Amal qilayotgan a'zolik bo'lsa — ustiga qo'shamiz
    start = membership.expires_at if (membership.expires_at and membership.expires_at > now) else now
    membership.expires_at = start + timedelta(days=days)
    membership.status = Membership.Status.ACTIVE
    membership.save(update_fields=["status", "expires_at"])
    return membership


def mark_paid(payment, provider_txn_id=""):
    """To'lovni muvaffaqiyatli deb belgilaydi (takroriy chaqiruvga xavfsiz)."""
    if payment.status == Payment.Status.SUCCESS:
        return payment
    payment.status = Payment.Status.SUCCESS
    if provider_txn_id:
        payment.provider_transaction_id = str(provider_txn_id)
    payment.save(update_fields=["status", "provider_transaction_id", "updated_at"])
    activate_membership(payment.user)
    return payment


# ---------------------------------------------------------------------------
# 1) To'lovni boshlash
# ---------------------------------------------------------------------------


class PaymentCreateView(APIView):
    """`POST /payments/create/` -> {payment_id, checkout_url, test_mode}"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        provider = (request.data.get("provider") or "").lower().strip()
        if provider not in (Payment.Provider.PAYME, Payment.Provider.CLICK):
            return Response(
                {"detail": "provider 'payme' yoki 'click' bo'lishi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = Decimal(str(request.data.get("amount") or MEMBERSHIP_PRICE))
        except (TypeError, ValueError):
            return Response({"detail": "Summa noto'g'ri."}, status=400)
        if amount <= 0:
            return Response({"detail": "Summa noldan katta bo'lishi kerak."}, status=400)

        payment = Payment.objects.create(
            user=request.user,
            amount=amount,
            provider=provider,
            status=Payment.Status.PENDING,
        )

        checkout_url = gateways.build_checkout_url(
            provider,
            payment.id,
            amount,
            return_url=request.data.get("return_url"),
        )

        return Response(
            {
                "payment_id": str(payment.id),
                "checkout_url": checkout_url,
                "amount": str(amount),
                "provider": provider,
                "test_mode": gateways.is_test_mode(provider),
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentStatusView(APIView):
    """Ilova to'lov holatini so'rab turadi."""

    permission_classes = [IsAuthenticated]

    def get(self, request, payment_id):
        payment = get_object_or_404(Payment, pk=payment_id, user=request.user)
        return Response({"payment_id": str(payment.id), "status": payment.status})


# ---------------------------------------------------------------------------
# 2) Test rejimidagi to'lov sahifasi
# ---------------------------------------------------------------------------


class TestPaymentView(APIView):
    """Faqat test rejimida ishlaydi — to'lovni qo'lda tasdiqlash/bekor qilish.

    Haqiqiy kredensiallar qo'yilganda bu endpoint 404 qaytaradi.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def _guard(self):
        return gateways.is_test_mode()

    def get(self, request, payment_id):
        if not self._guard():
            return Response({"detail": "Topilmadi."}, status=404)
        payment = get_object_or_404(Payment, pk=payment_id)
        return Response(
            {
                "payment_id": str(payment.id),
                "amount": str(payment.amount),
                "provider": payment.provider,
                "status": payment.status,
                "hint": "To'lovni tasdiqlash uchun shu manzilga POST yuboring "
                "({'action': 'pay'}) yoki bekor qilish uchun {'action': 'cancel'}.",
            }
        )

    def post(self, request, payment_id):
        if not self._guard():
            return Response({"detail": "Topilmadi."}, status=404)
        payment = get_object_or_404(Payment, pk=payment_id)
        action = (request.data.get("action") or "pay").lower()

        if action == "cancel":
            payment.status = Payment.Status.FAILED
            payment.failure_reason = "Test rejimida bekor qilindi"
            payment.save(update_fields=["status", "failure_reason", "updated_at"])
        else:
            mark_paid(payment, provider_txn_id=f"test-{payment.id}")

        return Response({"payment_id": str(payment.id), "status": payment.status})


# ---------------------------------------------------------------------------
# 3) Payme webhook (JSON-RPC)
# ---------------------------------------------------------------------------


class PaymeCallbackView(APIView):
    """Payme Merchant API. Barcha metodlar bitta endpointga JSON-RPC bilan keladi."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not gateways.check_payme_auth(request.headers.get("Authorization")):
            return Response(
                gateways.payme_error(gateways.PaymeError.ACCESS_DENIED, "Ruxsat yo'q")
            )

        body = request.data or {}
        method = body.get("method")
        params = body.get("params") or {}
        req_id = body.get("id")

        handler = {
            "CheckPerformTransaction": self._check_perform,
            "CreateTransaction": self._create,
            "PerformTransaction": self._perform,
            "CancelTransaction": self._cancel,
            "CheckTransaction": self._check,
        }.get(method)

        if handler is None:
            return Response(
                gateways.payme_error(
                    gateways.PaymeError.METHOD_NOT_FOUND, "Metod topilmadi", req_id
                )
            )
        return Response(handler(params, req_id))

    # -- yordamchi --
    def _find_payment(self, params):
        order_id = (params.get("account") or {}).get("order_id")
        if not order_id:
            return None
        return Payment.objects.filter(pk=order_id).first()

    def _ms(self, dt):
        return int(dt.timestamp() * 1000)

    # -- metodlar --
    def _check_perform(self, params, req_id):
        payment = self._find_payment(params)
        if payment is None:
            return gateways.payme_error(
                gateways.PaymeError.ORDER_NOT_FOUND, "Buyurtma topilmadi", req_id
            )
        if int(params.get("amount") or 0) != int(payment.amount * 100):
            return gateways.payme_error(
                gateways.PaymeError.INVALID_AMOUNT, "Summa mos emas", req_id
            )
        return {"result": {"allow": True}, "id": req_id}

    def _create(self, params, req_id):
        payment = self._find_payment(params)
        if payment is None:
            return gateways.payme_error(
                gateways.PaymeError.ORDER_NOT_FOUND, "Buyurtma topilmadi", req_id
            )
        if int(params.get("amount") or 0) != int(payment.amount * 100):
            return gateways.payme_error(
                gateways.PaymeError.INVALID_AMOUNT, "Summa mos emas", req_id
            )
        payment.provider_transaction_id = params.get("id")
        payment.save(update_fields=["provider_transaction_id", "updated_at"])
        return {
            "result": {
                "create_time": self._ms(payment.created_at),
                "transaction": str(payment.id),
                "state": 1,
            },
            "id": req_id,
        }

    def _perform(self, params, req_id):
        payment = Payment.objects.filter(provider_transaction_id=params.get("id")).first()
        if payment is None:
            return gateways.payme_error(
                gateways.PaymeError.TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi", req_id
            )
        mark_paid(payment, provider_txn_id=params.get("id"))
        return {
            "result": {
                "transaction": str(payment.id),
                "perform_time": self._ms(payment.updated_at),
                "state": 2,
            },
            "id": req_id,
        }

    def _cancel(self, params, req_id):
        payment = Payment.objects.filter(provider_transaction_id=params.get("id")).first()
        if payment is None:
            return gateways.payme_error(
                gateways.PaymeError.TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi", req_id
            )
        payment.status = Payment.Status.REFUNDED if payment.status == Payment.Status.SUCCESS else Payment.Status.FAILED
        payment.failure_reason = "Payme orqali bekor qilindi"
        payment.save(update_fields=["status", "failure_reason", "updated_at"])
        return {
            "result": {
                "transaction": str(payment.id),
                "cancel_time": self._ms(payment.updated_at),
                "state": -2 if payment.status == Payment.Status.REFUNDED else -1,
            },
            "id": req_id,
        }

    def _check(self, params, req_id):
        payment = Payment.objects.filter(provider_transaction_id=params.get("id")).first()
        if payment is None:
            return gateways.payme_error(
                gateways.PaymeError.TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi", req_id
            )
        state = 2 if payment.status == Payment.Status.SUCCESS else 1
        return {
            "result": {
                "create_time": self._ms(payment.created_at),
                "perform_time": self._ms(payment.updated_at) if state == 2 else 0,
                "cancel_time": 0,
                "transaction": str(payment.id),
                "state": state,
                "reason": None,
            },
            "id": req_id,
        }


# ---------------------------------------------------------------------------
# 4) Click webhook (Prepare / Complete)
# ---------------------------------------------------------------------------


class ClickCallbackView(APIView):
    """Click Shop API — `action=0` Prepare, `action=1` Complete."""

    permission_classes = [AllowAny]
    authentication_classes = []

    ERR_OK = 0
    ERR_SIGN = -1
    ERR_NOT_FOUND = -5
    ERR_AMOUNT = -2
    ERR_ALREADY = -4

    def post(self, request):
        data = request.data or {}
        action = str(data.get("action", ""))

        if not gateways.check_click_signature(data, action):
            return Response({"error": self.ERR_SIGN, "error_note": "Imzo noto'g'ri"})

        payment = Payment.objects.filter(pk=data.get("merchant_trans_id")).first()
        if payment is None:
            return Response({"error": self.ERR_NOT_FOUND, "error_note": "To'lov topilmadi"})

        try:
            amount = Decimal(str(data.get("amount")))
        except (TypeError, ValueError):
            return Response({"error": self.ERR_AMOUNT, "error_note": "Summa noto'g'ri"})
        if abs(amount - payment.amount) > Decimal("0.01"):
            return Response({"error": self.ERR_AMOUNT, "error_note": "Summa mos emas"})

        base = {
            "click_trans_id": data.get("click_trans_id"),
            "merchant_trans_id": str(payment.id),
            "error": self.ERR_OK,
            "error_note": "Success",
        }

        if action == "0":  # Prepare
            return Response({**base, "merchant_prepare_id": str(payment.id)})

        if action == "1":  # Complete
            if payment.status == Payment.Status.SUCCESS:
                return Response({**base, "merchant_confirm_id": str(payment.id)})
            mark_paid(payment, provider_txn_id=data.get("click_trans_id"))
            return Response({**base, "merchant_confirm_id": str(payment.id)})

        return Response({"error": self.ERR_SIGN, "error_note": "Noma'lum action"})
