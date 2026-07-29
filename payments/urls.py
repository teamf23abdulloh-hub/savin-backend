from django.urls import path
from rest_framework.routers import DefaultRouter

from payments.gateway_views import (
    ClickCallbackView,
    PaymeCallbackView,
    PaymentCreateView,
    PaymentStatusView,
    TestPaymentView,
)
from payments.views import (
    AdminFailedPaymentsView,
    AdminMonthlyRevenueView,
    AdminPaymentExportView,
    AdminPaymentViewSet,
    AdminRefundListView,
    AdminRefundReviewView,
    MyPaymentsView,
    PaymentRetryView,
    RefundRequestCreateView,
)

router = DefaultRouter()
router.register("admin/payments", AdminPaymentViewSet, basename="admin-payments")

urlpatterns = [
    # --- To'lov tizimlari (Payme / Click) ---
    path("payments/create/", PaymentCreateView.as_view(), name="payment-create"),
    path(
        "payments/status/<uuid:payment_id>/",
        PaymentStatusView.as_view(),
        name="payment-status",
    ),
    # Provayder webhook'lari (autentifikatsiya provayder imzosi orqali)
    path("payments/payme/callback/", PaymeCallbackView.as_view(), name="payme-callback"),
    path("payments/click/callback/", ClickCallbackView.as_view(), name="click-callback"),
    # Faqat test rejimida ochiq (kredensiallar qo'yilsa 404)
    path(
        "payments/test/<uuid:payment_id>/",
        TestPaymentView.as_view(),
        name="payment-test",
    ),
    # aniq (static) yo'llar HAR DOIM avval
    path(
        "admin/payments/failed/",
        AdminFailedPaymentsView.as_view(),
        name="admin-payments-failed",
    ),
    path(
        "admin/payments/monthly-revenue/",
        AdminMonthlyRevenueView.as_view(),
        name="admin-payments-monthly",
    ),
    path(
        "admin/payments/export/",
        AdminPaymentExportView.as_view(),
        name="admin-payments-export",
    ),
    path("payments/", MyPaymentsView.as_view(), name="my-payments"),
    path("payments/<uuid:pk>/retry/", PaymentRetryView.as_view(), name="payment-retry"),
    path(
        "payments/<uuid:pk>/refund/",
        RefundRequestCreateView.as_view(),
        name="payment-refund",
    ),
    path("admin/refunds/", AdminRefundListView.as_view(), name="admin-refunds"),
    path(
        "admin/refunds/<uuid:pk>/review/",
        AdminRefundReviewView.as_view(),
        name="admin-refund-review",
    ),
] + router.urls
