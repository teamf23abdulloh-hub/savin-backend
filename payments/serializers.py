from rest_framework import serializers

from payments.models import Payment, RefundRequest


class PaymentSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "user", "user_email", "amount", "provider", "provider_transaction_id",
            "status", "failure_reason", "is_retry", "original_payment", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class PaymentRetrySerializer(serializers.Serializer):
    """Qayta urinish."""


class RefundRequestCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class RefundRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundRequest
        fields = [
            "id", "payment", "requested_by", "reason", "status",
            "reviewed_by", "reviewed_at", "created_at",
        ]
        read_only_fields = fields


class RefundReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])


class MonthlyRevenueSerializer(serializers.Serializer):
    """Oylik daromad ko'rish."""

    month = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    successful_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
