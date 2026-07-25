from django.contrib import admin
from django.utils.html import format_html
from .models import Transaction, TransactionLog, DailyTransactionStat


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'customer_name', 'service_name', 
        'base_price_display', 'discount_display', 
        'final_price_display', 'status_colored', 'created_at'
    )
    list_filter = ('status', 'created_at', 'discount_percent', 'business')
    search_fields = ('customer_name', 'service_name', 'customer_phone')
    readonly_fields = ('discount_amount', 'final_price', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('business', 'cashier')
        }),
        ('Mijoz ma\'lumotlari', {
            'fields': ('customer_name', 'customer_phone')
        }),
        ('Xizmat ma\'lumotlari', {
            'fields': ('service_name', 'service_category')
        }),
        ('Narx ma\'lumotlari', {
            'fields': (
                'base_price', 'discount_percent',
                'discount_amount', 'final_price'
            )
        }),
        ('Holati', {
            'fields': ('status', 'notes')
        }),
        ('Vaqt', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def base_price_display(self, obj):
        return f"{obj.base_price:,.0f}"
    base_price_display.short_description = "Asl narx"
    
    def discount_display(self, obj):
        return f"{obj.discount_percent}% ({obj.discount_amount:,.0f})"
    discount_display.short_description = "Chegirma"
    
    def final_price_display(self, obj):
        return f"{obj.final_price:,.0f}"
    final_price_display.short_description = "To'lanagan"
    
    def status_colored(self, obj):
        colors = {
            'completed': '#28a745',
            'cancelled': '#dc3545',
            'refunded': '#ffc107',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            f'<span style="color: white; background-color: {color}; '
            f'padding: 3px 8px; border-radius: 3px;">{obj.get_status_display()}</span>'
        )
    status_colored.short_description = "Holati"
    
    actions = ['mark_as_cancelled', 'mark_as_refunded']
    
    def mark_as_cancelled(self, request, queryset):
        count = queryset.update(status='cancelled')
        self.message_user(request, f'{count} ta tranzaksiya bekor qilindi')
    mark_as_cancelled.short_description = "Bekor qilish"
    
    def mark_as_refunded(self, request, queryset):
        count = queryset.update(status='refunded')
        self.message_user(request, f'{count} ta tranzaksiyada refund qilindi')
    mark_as_refunded.short_description = "Refund qilish"


@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction', 'action', 'changed_by', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('transaction__customer_name', 'changed_by__email')
    readonly_fields = ('transaction', 'action', 'changed_by', 'timestamp', 'old_values', 'new_values')
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DailyTransactionStat)
class DailyTransactionStatAdmin(admin.ModelAdmin):
    list_display = (
        'date', 'business', 'total_transactions',
        'total_base_amount_display', 'total_discount_amount_display',
        'total_final_amount_display', 'average_discount_percent'
    )
    list_filter = ('date', 'business')
    readonly_fields = (
        'total_transactions', 'total_base_amount',
        'total_discount_amount', 'total_final_amount',
        'average_discount_percent', 'created_at', 'updated_at'
    )
    
    def total_base_amount_display(self, obj):
        return f"{obj.total_base_amount:,.0f}"
    total_base_amount_display.short_description = "Jami asl narx"
    
    def total_discount_amount_display(self, obj):
        return f"{obj.total_discount_amount:,.0f}"
    total_discount_amount_display.short_description = "Jami chegirma"
    
    def total_final_amount_display(self, obj):
        return f"{obj.total_final_amount:,.0f}"
    total_final_amount_display.short_description = "Jami to'lanagan"
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False