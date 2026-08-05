from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from mobileapi.views import (
    MobileActivityPingView,
    MobileBusinessListView,
    MobileCategoryListView,
    MobileLoginView,
    MobileMeView,
    MobileMembershipActivateView,
    MobileNotificationListView,
    MobileNotificationReadAllView,
    MobileRegisterView,
    MobileReferralOverviewView,
    MobileReferralRequestView,
    MobileReferralReviewBridgeView,
    MobileReferralStatusView,
    MobileTransactionStatsView,
    MobileTransactionView,
    RedeemCodeView,
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

    # Kassaga aytiladigan 4 xonali kod (QR o'rniga)
    path("redeem-code/", RedeemCodeView.as_view(), name="mobile-redeem-code"),

    # Bildirishnomalar
    path("notifications/", MobileNotificationListView.as_view(), name="mobile-notifications"),
    path("notifications/read-all/", MobileNotificationReadAllView.as_view(), name="mobile-notifications-read-all"),

    # Premium a'zolik (demo)
    path("membership/activate/", MobileMembershipActivateView.as_view(), name="mobile-membership-activate"),

    # Faollik signali — taklif qilingan do'stning 7 kunlik hisobi uchun
    path("activity/ping/", MobileActivityPingView.as_view(), name="mobile-activity-ping"),

    # Referal: kod, havola, do'stlar holati va mukofot so'rovi
    path("referral/overview/", MobileReferralOverviewView.as_view(), name="mobile-referral-overview"),
    path("referral/request/", MobileReferralRequestView.as_view(), name="mobile-referral-request"),
    path("referral/status/", MobileReferralStatusView.as_view(), name="mobile-referral-status"),
    # SMS sozlamalari holati (tashxis)
    path("sms-status/", SmsStatusView.as_view(), name="mobile-sms-status"),

    # Admin panel qarori (tasdiqlash/rad etish) shu yerga qaytadi (bridge)
    path("bridge/referral-review/", MobileReferralReviewBridgeView.as_view(), name="mobile-referral-review-bridge"),
]
