from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.models import CategoryActivityStat, DailyStatSnapshot
from analytics.serializers import (
    AdminDashboardSerializer,
    CategoryActivityStatSerializer,
    ChurnRateSerializer,
    DailyStatSnapshotSerializer,
)
from businesses.models import Business
from users.models import User
from users.permissions import IsAdminRole


class AdminDashboardView(APIView):
    """
    Admin panel Dashboard: DAU/MAU, Konversiya, Bizneslar, Foydalanuvchilar.
    """

    permission_classes = [IsAdminRole]

    def get(self, request):
        latest = DailyStatSnapshot.objects.order_by("-date").first()
        data = {
            "dau": latest.dau if latest else 0,
            "mau": latest.mau if latest else 0,
            "total_businesses": Business.objects.filter(is_active=True).count(),
            "total_users": User.objects.count(),
            "conversion_rate": latest.conversion_rate if latest else 0,
        }
        return Response(AdminDashboardSerializer(data).data)


class DailyStatSnapshotListView(generics.ListAPIView):
    """DAU / MAU grafigi uchun tarixiy ma'lumot."""

    queryset = DailyStatSnapshot.objects.all()
    serializer_class = DailyStatSnapshotSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["date"]


class CategoryActivityStatListView(generics.ListAPIView):
    """Kategoriya bo'yicha faollik."""

    queryset = CategoryActivityStat.objects.select_related("category").all()
    serializer_class = CategoryActivityStatSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["date", "category"]


class ChurnRateView(generics.ListAPIView):
    """Churn rate (Mijozlar ketish darajasi)."""

    permission_classes = [IsAdminRole]
    serializer_class = ChurnRateSerializer

    def get_queryset(self):
        return []

    def list(self, request, *args, **kwargs):
        snapshots = DailyStatSnapshot.objects.order_by("-date")[:30]
        data = [
            {"date": s.date, "churn_rate": s.churn_rate, "churned_users": s.churned_users}
            for s in snapshots
        ]
        return Response(ChurnRateSerializer(data, many=True).data)


class ConversionStatsView(APIView):
    """Konversiya (yuklab oldi -> to'ladi)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        snapshots = DailyStatSnapshot.objects.order_by("-date")[:30]
        data = [
            {
                "date": s.date,
                "downloads_count": s.downloads_count,
                "paid_count": s.paid_count,
                "conversion_rate": s.conversion_rate,
            }
            for s in snapshots
        ]
        return Response(data)


class DiscountVolumeStatsView(APIView):
    """Chegirma hajmi (umumiy tejash)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        snapshots = DailyStatSnapshot.objects.order_by("-date")[:30]
        data = [{"date": s.date, "total_discount_amount": s.total_discount_amount} for s in snapshots]
        return Response(data)
