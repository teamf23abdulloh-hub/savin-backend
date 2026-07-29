from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("analytics/", views.AnalyticsView.as_view(), name="analytics"),
    path("analytics/export/", views.AnalyticsExportView.as_view(), name="analytics-export"),
    path("users/", views.MemberListView.as_view(), name="users-list"),
    path("users/stats/", views.MemberStatsView.as_view(), name="users-stats"),
    path("users/export/", views.MemberExportView.as_view(), name="users-export"),
    path("users/<int:pk>/", views.MemberDetailView.as_view(), name="users-detail"),
    path("users/<int:pk>/block/", views.MemberBlockView.as_view(), name="users-block"),
    path("users/<int:pk>/extend/", views.MemberExtendView.as_view(), name="users-extend"),
    path("users/<int:pk>/referral-requests/", views.MemberReferralRequestsView.as_view(), name="users-referral-requests"),
    path("businesses/", views.BusinessListCreateView.as_view(), name="businesses-list"),
    path("businesses/stats/", views.BusinessStatsView.as_view(), name="businesses-stats"),
    path("businesses/export/", views.BusinessExportView.as_view(), name="businesses-export"),
    path("businesses/<int:pk>/", views.BusinessDetailView.as_view(), name="businesses-detail"),
    path("businesses/<int:pk>/approve/", views.BusinessApproveView.as_view(), name="businesses-approve"),
    path("businesses/<int:pk>/reject/", views.BusinessRejectView.as_view(), name="businesses-reject"),
    path("businesses/<int:pk>/block/", views.BusinessBlockView.as_view(), name="businesses-block"),
    path(
        "businesses/<int:pk>/transactions/",
        views.BusinessTransactionsView.as_view(),
        name="businesses-transactions",
    ),
    path("businesses/<int:pk>/requests/", views.BusinessRequestListView.as_view(), name="businesses-requests"),
    # Biznes egasi o'z panelida yaratgan chegirmalar
    path("businesses/<int:pk>/discounts/", views.BusinessDiscountsView.as_view(), name="businesses-discounts"),
    path("business-requests/<int:pk>/approve/", views.BusinessRequestApproveView.as_view(), name="business-requests-approve"),
    path("business-requests/<int:pk>/reject/", views.BusinessRequestRejectView.as_view(), name="business-requests-reject"),
    path("applications/", views.ApplicationListView.as_view(), name="applications-list"),
    path("applications/<int:pk>/", views.ApplicationUpdateView.as_view(), name="applications-update"),
    path("applications/<int:pk>/approve/", views.ApplicationApproveView.as_view(), name="applications-approve"),
    path("applications/<int:pk>/reject/", views.ApplicationRejectView.as_view(), name="applications-reject"),
    path("payments/", views.PaymentListView.as_view(), name="payments-list"),
    path("payments/stats/", views.PaymentStatsView.as_view(), name="payments-stats"),
    path("payments/charts/", views.PaymentChartsView.as_view(), name="payments-charts"),
    path("payments/export/", views.PaymentExportView.as_view(), name="payments-export"),
    path("payments/<str:txn_id>/", views.PaymentDetailView.as_view(), name="payments-detail"),
    path("payments/<str:txn_id>/refund/", views.PaymentRefundView.as_view(), name="payments-refund"),
    path("notifications/", views.NotificationListCreateView.as_view(), name="notifications-list-create"),
    path("notifications/meta/", views.NotificationMetaView.as_view(), name="notifications-meta"),
    path("notifications/<int:pk>/", views.NotificationDeleteView.as_view(), name="notifications-delete"),
    path("alerts/", views.AdminAlertListView.as_view(), name="alerts-list"),
    path("alerts/read-all/", views.AdminAlertMarkReadView.as_view(), name="alerts-read-all"),
    path("alerts/<int:pk>/read/", views.AdminAlertMarkReadView.as_view(), name="alerts-read"),
    path("public/business-applications/", views.LandingBusinessApplyView.as_view(), name="landing-business-apply"),
    path("public/business-notifications/", views.BusinessEventNotifyView.as_view(), name="business-event-notify"),

    # Referal mukofot so'rovlari
    path("public/referral-requests/", views.ReferralRequestReceiveView.as_view(), name="referral-request-receive"),
    path("referral-requests/", views.ReferralRequestListView.as_view(), name="referral-requests-list"),
    path("referral-requests/<int:pk>/approve/", views.ReferralRequestApproveView.as_view(), name="referral-requests-approve"),
    path("referral-requests/<int:pk>/reject/", views.ReferralRequestRejectView.as_view(), name="referral-requests-reject"),

    # Landing sayti uchun ochiq statistika (haqiqiy raqamlar)
    path("public/stats/", views.PublicStatsView.as_view(), name="public-stats"),
]
