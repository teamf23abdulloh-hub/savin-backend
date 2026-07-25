from rest_framework import serializers

from .models import AdminUser, NotificationPreference, AccountSettings


class AdminUserSerializer(serializers.ModelSerializer):
    login = serializers.CharField(source="username", read_only=True)

    class Meta:
        model = AdminUser
        fields = ["id", "login", "first_name", "last_name", "email", "phone"]


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminUser
        fields = ["first_name", "last_name", "email", "phone"]


class AdminUserCreateSerializer(serializers.ModelSerializer):
    """Used by an existing admin to create another admin operator account."""

    login = serializers.CharField(source="username")
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = AdminUser
        fields = ["login", "password", "first_name", "last_name", "email", "phone"]

    def validate_login(self, value):
        if AdminUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("Bu login band, boshqasini tanlang.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = AdminUser(is_staff=True, **validated_data)
        user.set_password(password)
        user.save()
        return user


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ["new_user", "new_payment", "new_business_application", "weekly_report"]


class AccountSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountSettings
        fields = ["two_factor_enabled", "language", "dark_mode"]
