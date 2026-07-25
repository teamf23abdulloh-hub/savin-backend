from django.contrib import admin

from discounts.models import DiscountChangeRequest, DiscountUsage


@admin.register(DiscountChangeRequest)
class DiscountChangeRequestAdmin(admin.ModelAdmin):
    list_display = ("business", "old_percent", "new_percent", "status", "created_at")
    list_filter = ("status",)


@admin.register(DiscountUsage)
class DiscountUsageAdmin(admin.ModelAdmin):
    list_display = ("business", "customer", "cashier", "applied_percent", "purchase_amount", "used_at")
    list_filter = ("business",)
    search_fields = ("customer__email",)
