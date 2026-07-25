from decimal import Decimal

from rest_framework import serializers

from discounts.models import DiscountChangeRequest, DiscountUsage


class DiscountChangeRequestCreateSerializer(serializers.Serializer):
    """Foiz o'zgartirish so'rovi (Biznes egasi -> Admin)."""

    new_percent = serializers.IntegerField(min_value=1, max_value=100)
    reason = serializers.CharField(required=False, allow_blank=True)


class DiscountChangeRequestSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="business.name", read_only=True)

    class Meta:
        model = DiscountChangeRequest
        fields = [
            "id", "business", "business_name", "requested_by", "old_percent", "new_percent",
            "reason", "status", "reviewed_by", "reviewed_at", "created_at",
        ]
        read_only_fields = fields


class DiscountChangeReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])


class DiscountUsageSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    cashier_name = serializers.CharField(source="cashier.full_name", read_only=True)

    class Meta:
        model = DiscountUsage
        fields = [
            "id", "business", "customer", "customer_email", "cashier", "cashier_name",
            "applied_percent", "purchase_amount", "discount_amount", "used_at",
        ]
        read_only_fields = ["id", "used_at"]


class DiscountUsageCreateSerializer(serializers.Serializer):
    """Kassir tomonidan chegirma qo'llash (mijoz keldi -> chegirma berildi)."""

    # QR skanerlashdan keladigan mijoz ID'si (ustuvor) yoki qo'lda kiritilgan email
    customer_id = serializers.UUIDField(required=False)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    purchase_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )


class DiscountStatSerializer(serializers.Serializer):
    """Statistika: Hafta/oy grafigi."""

    period = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_transactions = serializers.IntegerField()


# ---------------- KASSIR PANELI ----------------


class QrScanSerializer(serializers.Serializer):
    """QR skanerlash: mijoz QR kodidan o'qilgan qiymat (mijoz ID yoki email).

    Frontend `qr_code` nomi bilan yuboradi, eski mijozlar `qr_data` bilan —
    ikkalasi ham qabul qilinadi.
    """

    qr_data = serializers.CharField(max_length=255, required=False, allow_blank=True)
    qr_code = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        value = (attrs.get("qr_data") or attrs.get("qr_code") or "").strip()
        if not value:
            raise serializers.ValidationError(
                {"qr_code": "QR kod qiymati yuborilmadi."}
            )
        attrs["value"] = value
        return attrs


class CashierDashboardSerializer(serializers.Serializer):
    """Kassir dashboard: bugungi tashriflar va summalar."""

    today_visits = serializers.IntegerField()
    my_today_visits = serializers.IntegerField()
    today_discount_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    today_paid_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    current_percent = serializers.IntegerField(allow_null=True)
