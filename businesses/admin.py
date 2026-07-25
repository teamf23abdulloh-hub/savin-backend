from django.contrib import admin

from businesses.models import Application, Business, Cashier, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("business_name", "applicant", "status", "current_step", "created_at")
    list_filter = ("status", "business_type", "category")
    search_fields = ("business_name", "applicant__email", "phone_number")


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "partnership_status", "is_active", "created_at")
    list_filter = ("partnership_status", "is_active", "category")
    search_fields = ("name", "owner__email")


@admin.register(Cashier)
class CashierAdmin(admin.ModelAdmin):
    list_display = ("full_name", "business", "user", "is_active", "added_at")
    list_filter = ("is_active",)
