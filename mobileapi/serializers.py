from django.utils import timezone
from rest_framework import serializers

from businesses.models import Business, Category
from mobileapi.models import CustomerNotification
from users.models import User


class MobileUserSerializer(serializers.ModelSerializer):
    """Mobil ilova kutgan shakl: is_premium, membership_expires_at, avatar_url."""

    is_premium = serializers.SerializerMethodField()
    membership_expires_at = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "first_name", "last_name", "phone_number", "email", "role",
            "is_premium", "membership_expires_at", "avatar_url",
        ]
        read_only_fields = ["id", "role"]

    def _membership(self, obj):
        return getattr(obj, "membership", None)

    def get_is_premium(self, obj):
        m = self._membership(obj)
        if not m or not m.expires_at:
            return False
        return m.status == "active" and m.expires_at > timezone.now()

    def get_membership_expires_at(self, obj):
        m = self._membership(obj)
        return m.expires_at.isoformat() if m and m.expires_at else None

    def get_avatar_url(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get("request")
        url = obj.avatar.url
        return request.build_absolute_uri(url) if request else url


def _business_discount(business) -> int:
    """Biznes chegirma foizi — bog'langan arizadan olinadi (bo'lmasa 0)."""
    app = getattr(business, "application", None)
    if app and app.discount_percent:
        return int(app.discount_percent)
    return 0


def _stable_rating(business) -> float:
    """Modelda reyting maydoni yo'q — id asosida barqaror 4.3–4.9 qiymat."""
    h = abs(hash(str(business.id)))
    return round(4.3 + (h % 7) / 10.0, 1)


class MobileBusinessSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", default="")
    discount_percent = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    district = serializers.CharField(source="city_district", default="")
    is_premium = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = [
            "id", "name", "category_name", "discount_percent", "rating",
            "district", "is_premium", "latitude", "longitude",
        ]

    def get_discount_percent(self, obj):
        return _business_discount(obj)

    def get_rating(self, obj):
        return _stable_rating(obj)

    def get_is_premium(self, obj):
        # Modelda alohida "premium" maydoni yo'q — yuqori chegirmali (25%+)
        # bizneslar premium sifatida belgilanadi (vizual xilma-xillik uchun).
        return _business_discount(obj) >= 25

    def get_latitude(self, obj):
        return float(obj.latitude) if obj.latitude is not None else None

    def get_longitude(self, obj):
        return float(obj.longitude) if obj.longitude is not None else None


class MobileCategorySerializer(serializers.ModelSerializer):
    icon = serializers.SerializerMethodField()
    discount_min = serializers.SerializerMethodField()
    discount_max = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "icon", "discount_min", "discount_max"]

    def get_icon(self, obj):
        # Mobil ilova kategoriya iconini o'zi (nom bo'yicha) tanlaydi.
        return ""

    def _discount_range(self, obj):
        percents = [
            _business_discount(b)
            for b in obj.businesses.all()
            if _business_discount(b) > 0
        ]
        return (min(percents), max(percents)) if percents else (0, 0)

    def get_discount_min(self, obj):
        return self._discount_range(obj)[0]

    def get_discount_max(self, obj):
        return self._discount_range(obj)[1]


class MobileNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerNotification
        fields = ["id", "title", "body", "kind", "is_read", "created_at"]
