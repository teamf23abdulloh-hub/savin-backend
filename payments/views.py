import csv

from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import Payment, RefundRequest
from payments.serializers import (
    MonthlyRevenueSerializer,
    PaymentSerializer,
    RefundReviewSerializer,
    RefundRequestCreateSerializer,
    RefundRequestSerializer,
)
from users.permissions import IsAdminRole

# ==================== FOYDALANUVCHI: to'lovlar ====================


class MyPaymentsView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)


class PaymentRetryView(APIView):
    """Muvaffaqiyatsiz to'lovlar -> Qayta urinish."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        original = get_object_or_404(
            Payment, pk=pk, user=request.user, status=Payment.Status.FAILED
        )
        new_payment = Payment.objects.create(
            user=request.user,
            amount=original.amount,
            provider=original.provider,
            status=Payment.Status.PENDING,
            is_retry=True,
            original_payment=original,
        )
        # NOTE: bu yerda haqiqiy to'lov provayder (Click/Payme/Uzum) integratsiyasi chaqiriladi
        return Response(
            PaymentSerializer(new_payment).data, status=status.HTTP_201_CREATED
        )


class RefundRequestCreateView(APIView):
    """Refund so'rash (mijoz)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        payment = get_object_or_404(
            Payment, pk=pk, user=request.user, status=Payment.Status.SUCCESS
        )
        serializer = RefundRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refund = RefundRequest.objects.create(
            payment=payment,
            requested_by=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(
            RefundRequestSerializer(refund).data, status=status.HTTP_201_CREATED
        )


# ==================== ADMIN: To'lovlar boshqaruvi ====================


class AdminPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """To'lov tarixi (filter: sana, holat)."""

    queryset = Payment.objects.select_related("user").all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "provider"]
    search_fields = ["user__email", "provider_transaction_id"]
    ordering_fields = ["created_at", "amount"]


class AdminFailedPaymentsView(generics.ListAPIView):
    """Muvaffaqiyatsiz to'lovlar."""

    serializer_class = PaymentSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return Payment.objects.filter(status=Payment.Status.FAILED)


class AdminMonthlyRevenueView(APIView):
    """Oylik daromad ko'rish."""

    permission_classes = [IsAdminRole]

    # ✅ FIX: `get` metodi klass tashqarisida (modul darajasida) yozilib
    # qolgan edi — endpoint har doim 405 (Method Not Allowed) qaytarardi.
    def get(self, request):
        revenue_qs = (
            Payment.objects.filter(status=Payment.Status.SUCCESS)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total_revenue=Sum("amount"), successful_count=Count("id"))
        )
        failed_agg = (
            Payment.objects.filter(status=Payment.Status.FAILED)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(failed_count=Count("id"))
        )
        revenue_map = {row["month"]: row for row in revenue_qs}
        failed_map = {row["month"]: row["failed_count"] for row in failed_agg}

        all_months = sorted(set(revenue_map) | set(failed_map), reverse=True)
        data = [
            {
                "month": month.strftime("%Y-%m"),
                "total_revenue": revenue_map.get(month, {}).get("total_revenue") or 0,
                "successful_count": revenue_map.get(month, {}).get("successful_count") or 0,
                "failed_count": failed_map.get(month, 0),
            }
            for month in all_months
        ]
        serializer = MonthlyRevenueSerializer(data, many=True)
        return Response(serializer.data)


class AdminPaymentExportView(APIView):
    """Export (CSV, Excel)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = Payment.objects.select_related("user").all()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        status_filter = request.query_params.get("status")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        if status_filter:
            qs = qs.filter(status=status_filter)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="tolovlar.csv"'
        writer = csv.writer(response)
        writer.writerow(["Foydalanuvchi", "Summa", "Provayder", "Holat", "Sana"])
        for p in qs:
            writer.writerow(
                [
                    p.user.email,
                    p.amount,
                    p.provider,
                    p.status,
                    p.created_at.strftime("%Y-%m-%d %H:%M"),
                ]
            )
        return response


class AdminRefundReviewView(APIView):
    """Refund tasdiqlash."""

    permission_classes = [IsAdminRole]

    # ✅ FIX: `post` metodi klass tashqarisida yozilib qolgan edi —
    # endpoint har doim 405 qaytarardi (transaction importi ham klass
    # ichida qolib ketgan edi).
    def post(self, request, pk):
        refund = get_object_or_404(RefundRequest, pk=pk)
        serializer = RefundReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            refund.reviewed_by = request.user
            refund.reviewed_at = timezone.now()

            if serializer.validated_data["action"] == "approve":
                refund.status = RefundRequest.Status.APPROVED
                refund.payment.status = Payment.Status.REFUNDED
                refund.payment.save(update_fields=["status"])
            else:
                refund.status = RefundRequest.Status.REJECTED

            refund.save()

        return Response(RefundRequestSerializer(refund).data)


class AdminRefundListView(generics.ListAPIView):
    serializer_class = RefundRequestSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]
    queryset = RefundRequest.objects.select_related("payment", "requested_by").all()
