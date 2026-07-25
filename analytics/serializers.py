from rest_framework import serializers

from analytics.models import CategoryActivityStat, DailyStatSnapshot


class DailyStatSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyStatSnapshot
        fields = "__all__"


class CategoryActivityStatSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = CategoryActivityStat
        fields = ["id", "date", "category", "category_name", "views_count", "purchases_count"]


class AdminDashboardSerializer(serializers.Serializer):
    """Admin panel Dashboard: DAU/MAU, Konversiya, Bizneslar, Foydalanuvchilar."""

    dau = serializers.IntegerField()
    mau = serializers.IntegerField()
    total_businesses = serializers.IntegerField()
    total_users = serializers.IntegerField()
    conversion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class ChurnRateSerializer(serializers.Serializer):
    date = serializers.DateField()
    churn_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    churned_users = serializers.IntegerField()
