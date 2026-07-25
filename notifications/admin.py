from django.contrib import admin

from notifications.models import PushNotification, UserNotification


@admin.register(PushNotification)
class PushNotificationAdmin(admin.ModelAdmin):
    list_display = ("title_uz", "audience", "status", "scheduled_at", "sent_at", "created_at")
    list_filter = ("audience", "status")


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "notification_type", "is_read", "created_at")
    list_filter = ("notification_type", "is_read")
    search_fields = ("user__email", "title")
