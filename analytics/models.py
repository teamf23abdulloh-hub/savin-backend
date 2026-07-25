import uuid

from django.db import models


class DailyStatSnapshot(models.Model):
    """
    Har kunlik statistikalar snapshoti (DAU/MAU, konversiya, chegirma hajmi, churn rate).
    Har kuni cron/management command orqali yozib boriladi, Analitika bo'limida grafik uchun ishlatiladi.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True)

    dau = models.PositiveIntegerField(default=0)
    mau = models.PositiveIntegerField(default=0)

    new_users = models.PositiveIntegerField(default=0)
    new_businesses = models.PositiveIntegerField(default=0)

    downloads_count = models.PositiveIntegerField(default=0)  # yuklab oldi
    paid_count = models.PositiveIntegerField(default=0)  # to'ladi
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %

    total_discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    churned_users = models.PositiveIntegerField(default=0)
    churn_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Stats<{self.date}>"


class CategoryActivityStat(models.Model):
    """Kategoriya bo'yicha faollik statistikasi."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField()
    category = models.ForeignKey("businesses.Category", on_delete=models.CASCADE, related_name="activity_stats")
    views_count = models.PositiveIntegerField(default=0)
    purchases_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("date", "category")
        ordering = ["-date"]
