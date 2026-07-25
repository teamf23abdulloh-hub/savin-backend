from django.contrib import admin

from payments.models import Payment, RefundRequest


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "provider", "status", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("user__email", "provider_transaction_id")


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ("payment", "requested_by", "status", "created_at")
    list_filter = ("status",)
