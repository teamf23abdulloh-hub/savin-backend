from django.utils import timezone
from rest_framework import serializers

from notifications.models import PushNotification, UserNotification


class UserNotificationSerializer(serializers.ModelSerializer):
    """Bildirishnomalar: Yangi mijoz, chegirma, eslatma."""

    class Meta:
        model = UserNotification
        fields = ["id", "notification_type", "title", "body", "is_read", "created_at"]
        read_only_fields = fields


class PushNotificationCreateSerializer(serializers.ModelSerializer):
    """
    Qabul qiluvchi tanlash -> Alohida foydalanuvchi / Kategoriya bo'yicha / Hammaga
    Xabar yozish (UZ/RU/EN) -> Yuborish / Rejalashtirilgan yuborish
    """

    class Meta:
        model = PushNotification
        fields = [
            "id", "audience", "target_user", "target_category",
            "title_uz", "title_ru", "title_en",
            "body_uz", "body_ru", "body_en",
            "scheduled_at", "status", "sent_at", "created_at",
        ]
        read_only_fields = ["id", "status", "sent_at", "created_at"]

    def validate(self, attrs):
        audience = attrs.get("audience")
        if audience == PushNotification.Audience.SINGLE_USER and not attrs.get("target_user"):
            raise serializers.ValidationError({"target_user": "Alohida foydalanuvchi tanlanishi kerak."})
        if audience == PushNotification.Audience.CATEGORY and not attrs.get("target_category"):
            raise serializers.ValidationError({"target_category": "Kategoriya tanlanishi kerak."})
        return attrs

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        if validated_data.get("scheduled_at") and validated_data["scheduled_at"] > timezone.now():
            validated_data["status"] = PushNotification.Status.SCHEDULED
        return super().create(validated_data)


class PushNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushNotification
        fields = "__all__"
