from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from users.models import Membership, User, UserActivityLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "username", "role", "is_blocked", "is_active", "created_at")
    list_filter = ("role", "is_blocked", "is_active")
    search_fields = ("email", "username", "phone_number")
    ordering = ("-created_at",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Qo'shimcha", {"fields": ("role", "phone_number", "avatar", "is_2fa_enabled", "is_blocked", "blocked_reason")}),
    )


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "started_at", "expires_at")
    list_filter = ("status",)


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("user__email",)
