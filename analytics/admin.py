from django.contrib import admin

from analytics.models import CategoryActivityStat, DailyStatSnapshot


@admin.register(DailyStatSnapshot)
class DailyStatSnapshotAdmin(admin.ModelAdmin):
    list_display = ("date", "dau", "mau", "conversion_rate", "churn_rate")
    ordering = ("-date",)


@admin.register(CategoryActivityStat)
class CategoryActivityStatAdmin(admin.ModelAdmin):
    list_display = ("date", "category", "views_count", "purchases_count")
    list_filter = ("category",)
