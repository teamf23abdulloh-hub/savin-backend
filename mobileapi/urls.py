from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from mobileapi.views import (
    MobileBusinessListView,
    MobileCategoryListView,
    MobileLoginView,
    MobileMeView,
    MobileMembershipActivateView,
    MobileNotificationListView,
    MobileRegisterView,
    MobileReferralRequestView,
    MobileReferralReviewBridgeView,
    MobileReferralStatusView,
    MobileTransactionStatsView,
    MobileTransactionView,
    SmsStatusView,
)

# Barcha yo'llar config/urls.py da "api/v1/mobile/" ostida ulanadi.
urlpatterns = [
    # Auth (telefon + OTP)
    path("auth/register/", MobileRegisterView.as_view(), name="mobile-register"),
    path("auth/login/", MobileLoginView.as_view(), name="mobile-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="mobile-token-refresh"),
    path("me/", MobileMeView.as_view(), name="mobile-me"),

    # Katalog
    path("categories/", MobileCategoryListView.as_view(), name="mobile-categories"),
    path("businesses/", MobileBusinessListView.as_view(), name="mobile-businesses"),

    # Hamyon (tranzaksiyalar) — MUHIM: stats yo'li umumiy yo'ldan oldin turishi kerak
    path("transactions/stats/", MobileTransactionStatsView.as_view(), name="mobile-tx-stats"),
    path("transactions/", MobileTransactionView.as_view(), name="mobile-transactions"),

    # Bildirishnomalar
    path("notifications/", MobileNotificationListView.as_view(), name="mobile-notifications"),

    # Premium a'zolik (demo)
    path("membership/activate/", MobileMembershipActivateView.as_view(), name="mobile-membership-activate"),

    # Referal mukofot so'rovi
    path("referral/request/", MobileReferralRequestView.as_view(), name="mobile-referral-request"),
    path("referral/status/", MobileReferralStatusView.as_view(), name="mobile-referral-status"),
    # SMS sozlamalari holati (tashxis)
    path("sms-status/", SmsStatusView.as_view(), name="mobile-sms-status"),

    # Admin panel qarori (tasdiqlash/rad etish) shu yerga qaytadi (bridge)
    path("bridge/referral-review/", MobileReferralReviewBridgeView.as_view(), name="mobile-referral-review-bridge"),
]
