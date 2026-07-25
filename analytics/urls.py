from django.urls import path

from analytics.views import (
    AdminDashboardView,
    CategoryActivityStatListView,
    ChurnRateView,
    ConversionStatsView,
    DailyStatSnapshotListView,
    DiscountVolumeStatsView,
)

urlpatterns = [
    path("admin/dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("admin/analytics/daily-stats/", DailyStatSnapshotListView.as_view(), name="analytics-daily-stats"),
    path("admin/analytics/category-activity/", CategoryActivityStatListView.as_view(), name="analytics-category-activity"),
    path("admin/analytics/churn-rate/", ChurnRateView.as_view(), name="analytics-churn-rate"),
    path("admin/analytics/conversion/", ConversionStatsView.as_view(), name="analytics-conversion"),
    path("admin/analytics/discount-volume/", DiscountVolumeStatsView.as_view(), name="analytics-discount-volume"),
]
