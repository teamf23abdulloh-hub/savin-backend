from django.contrib import admin

from .models import AccountSettings, AdminToken, AdminUser, NotificationPreference


@admin.register(AdminUser)
class AdminUserAdmin(admin.ModelAdmin):
    """Admin operatorlari.

    `django.contrib.auth.admin.UserAdmin` ishlatilmaydi: u AUTH_USER_MODEL
    (`users.User`) uchun mo'ljallangan formalarga bog'langan, `AdminUser` esa
    endi AUTH_USER_MODEL emas. Operator hisoblari asosan React admin panelining
    "Adminlar" bo'limi orqali boshqariladi.
    """

    list_display = ("username", "first_name", "last_name", "email", "phone", "is_active")
    search_fields = ("username", "first_name", "last_name", "email", "phone")
    list_filter = ("is_active", "is_staff")


admin.site.register(NotificationPreference)
admin.site.register(AccountSettings)
admin.site.register(AdminToken)
