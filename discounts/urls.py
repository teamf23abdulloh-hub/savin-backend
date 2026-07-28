from django.urls import path
from rest_framework.routers import DefaultRouter

from discounts.views import (
    AdminBridgeDiscountReviewView,
    AdminDiscountChangeRequestViewSet,
    AdminDiscountChangeReviewView,
    CashierApplyDiscountView,
    CashierDashboardView,
    CashierMeView,
    CashierScanQrView,
    CashierVisitHistoryView,
    DiscountChangeRequestCreateView,
    DiscountHistoryExportView,
    DiscountHistoryView,
    DiscountStatisticsView,
    MyDiscountDetailView,
    MyDiscountInfoView,
    MyDiscountListCreateView,
    MyDiscountToggleView,
)

router = DefaultRouter()
router.register("admin/discount-requests", AdminDiscountChangeRequestViewSet, basename="admin-discount-requests")

urlpatterns = [
    # Chegirma turlari (kartalar) — biznes egasi uchun to'liq CRUD
    path("my-business/discounts/", MyDiscountListCreateView.as_view(), name="my-discounts"),
    path("my-business/discounts/<uuid:pk>/", MyDiscountDetailView.as_view(), name="my-discount-detail"),
    path("my-business/discounts/<uuid:pk>/toggle/", MyDiscountToggleView.as_view(), name="my-discount-toggle"),

    path("my-business/discount/", MyDiscountInfoView.as_view(), name="my-discount-info"),
    path("my-business/discount/change-request/", DiscountChangeRequestCreateView.as_view(), name="discount-change-request"),
    path("my-business/discount/history/", DiscountHistoryView.as_view(), name="discount-history"),
    path("my-business/discount/history/export/", DiscountHistoryExportView.as_view(), name="discount-history-export"),
    path("my-business/discount/statistics/", DiscountStatisticsView.as_view(), name="discount-statistics"),

    # ---- Kassir paneli ----
    path("cashier/me/", CashierMeView.as_view(), name="cashier-me"),
    path("cashier/dashboard/", CashierDashboardView.as_view(), name="cashier-dashboard"),
    path("cashier/visits/", CashierVisitHistoryView.as_view(), name="cashier-visits"),
    path("cashier/scan-qr/", CashierScanQrView.as_view(), name="cashier-scan-qr"),
    path("cashier/apply-discount/", CashierApplyDiscountView.as_view(), name="cashier-apply-discount"),

    path("admin/discount-requests/<uuid:pk>/review/", AdminDiscountChangeReviewView.as_view(), name="admin-discount-review"),
    # Admin panel backendidan keladigan chegirma so'rovi natijasi (bridge)
    path("public/admin-bridge/discount-requests/review/", AdminBridgeDiscountReviewView.as_view(), name="admin-bridge-discount-review"),
] + router.urls
