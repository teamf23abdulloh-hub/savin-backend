from django.urls import path
from rest_framework.routers import DefaultRouter

from notifications.views import (
    AdminPushNotificationSendView,
    AdminPushNotificationViewSet,
    MarkAllNotificationsReadView,
    MarkNotificationReadView,
    MyNotificationsView,
)

router = DefaultRouter()
router.register("admin/push-notifications", AdminPushNotificationViewSet, basename="admin-push-notifications")

urlpatterns = [
    path("notifications/", MyNotificationsView.as_view(), name="my-notifications"),
    path("notifications/<uuid:pk>/read/", MarkNotificationReadView.as_view(), name="notification-read"),
    path("notifications/read-all/", MarkAllNotificationsReadView.as_view(), name="notifications-read-all"),

    path(
        "admin/push-notifications/<uuid:pk>/send/",
        AdminPushNotificationSendView.as_view(),
        name="admin-push-send",
    ),
] + router.urls
