from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import Membership, User, UserActivityLog


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "phone_number", "role"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Kirish (Login): Email + Parol. Tasdiqlash, 2FA (ixtiyoriy)."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    otp_code = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        user = authenticate(email=attrs["email"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("Email yoki parol noto'g'ri.")
        if user.is_blocked:
            raise serializers.ValidationError("Foydalanuvchi bloklangan.")
        if user.is_2fa_enabled:
            if not attrs.get("otp_code"):
                raise serializers.ValidationError({"otp_code": "2FA kodi talab qilinadi."})
            # NOTE: haqiqiy OTP tekshiruvi uchun pyotp yoki SMS provayder ulanishi kerak
        attrs["user"] = user
        return attrs

    def get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["id", "status", "started_at", "expires_at"]


class UserSerializer(serializers.ModelSerializer):
    membership = MembershipSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "phone_number", "role", "avatar",
            "is_2fa_enabled", "is_blocked", "blocked_reason",
            "created_at", "last_seen_at", "membership",
        ]
        read_only_fields = ["id", "created_at", "role"]


class UserBasicSerializer(serializers.ModelSerializer):
    """Boshqa app'lar (masalan transactions) ichida nested/qisqa ko'rinishda
    foydalanuvchini ko'rsatish uchun — to'liq UserSerializer'dagi membership,
    faollik kabi og'ir maydonlarsiz."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "phone_number", "role"]


class AdminUserListSerializer(serializers.ModelSerializer):
    """Admin panel: Ro'yxatni ko'rish (filter, qidirish)."""

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "phone_number", "role",
            "is_blocked", "is_active", "created_at", "last_seen_at",
        ]


class AdminUserDetailSerializer(serializers.ModelSerializer):
    """Profilni ko'rish (membership, tarix)."""

    membership = MembershipSerializer(read_only=True)
    activity_logs = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "phone_number", "role",
            "is_blocked", "blocked_reason", "is_active",
            "created_at", "last_seen_at", "membership", "activity_logs",
        ]

    def get_activity_logs(self, obj):
        logs = obj.activity_logs.all()[:20]
        return [{"action": log.action, "created_at": log.created_at} for log in logs]


class BlockUserSerializer(serializers.Serializer):
    is_blocked = serializers.BooleanField()
    blocked_reason = serializers.CharField(required=False, allow_blank=True)


class MembershipUpdateSerializer(serializers.Serializer):
    """Membership uzaytirish / bekor qilish."""

    action = serializers.ChoiceField(choices=["extend", "cancel"])
    days = serializers.IntegerField(required=False, default=30)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])


# ---------------- SUPERADMIN: Adminlarni boshqarish ----------------


class AdminAccountSerializer(serializers.ModelSerializer):
    """Superadmin uchun: admin akkauntlar ro'yxati/tafsiloti."""

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "phone_number", "role",
            "is_blocked", "is_active", "created_at", "last_seen_at",
        ]
        read_only_fields = ["id", "created_at", "last_seen_at"]


class AdminAccountCreateSerializer(serializers.ModelSerializer):
    """Superadmin: yangi admin akkaunt yaratish."""

    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "phone_number"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(role=User.Role.ADMIN, **validated_data)
        user.set_password(password)
        user.save()
        return user
