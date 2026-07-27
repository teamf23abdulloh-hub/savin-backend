from django.utils import timezone
from rest_framework import serializers

from .models import (
    ReferralRequest,
    AdminAlert,
    Business,
    BusinessApplication,
    BusinessRequest,
    BusinessTransaction,
    Member,
    Notification,
    Payment,
    TransactionStatus,
)


def fmt_money(value):
    return f"{int(value):,} so'm"


def fmt_date(value):
    return value.strftime("%d.%m.%Y") if value else None


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


class MemberListSerializer(serializers.ModelSerializer):
    date = serializers.DateField(source="joined_at", format="%d.%m.%Y", read_only=True)
    savings = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = [
            "id",
            "member_code",
            "name",
            "phone",
            "city",
            "status",
            "activity_status",
            "date",
            "savings",
            "is_blocked",
        ]

    def get_savings(self, obj):
        return fmt_money(obj.savings_total)


class MemberPaymentSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source="created_at", format="%d.%m.%Y", read_only=True)

    class Meta:
        model = Payment
        fields = ["txn_id", "amount", "method", "status", "months", "date", "refund_reason"]

    def get_amount(self, obj):
        return fmt_money(obj.amount)


class MemberDetailSerializer(serializers.ModelSerializer):
    date = serializers.DateField(source="joined_at", format="%d.%m.%Y", read_only=True)
    membership_start_fmt = serializers.DateField(source="membership_start", format="%d.%m.%Y", read_only=True)
    membership_end_fmt = serializers.DateField(source="membership_end", format="%d.%m.%Y", read_only=True)
    blocked_at_fmt = serializers.DateField(source="blocked_at", format="%d.%m.%Y", read_only=True)
    extended_at_fmt = serializers.DateField(source="extended_at", format="%d.%m.%Y", read_only=True)
    savings = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    progress_pct = serializers.SerializerMethodField()
    next_payment = serializers.SerializerMethodField()
    payments = MemberPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Member
        fields = [
            "id",
            "member_code",
            "name",
            "phone",
            "city",
            "status",
            "activity_status",
            "date",
            "savings",
            "months_subscribed",
            "membership_start_fmt",
            "membership_end_fmt",
            "days_left",
            "progress_pct",
            "next_payment",
            "device",
            "push_enabled",
            "referral_code",
            "referral_invited",
            "referral_target",
            "is_blocked",
            "block_reason",
            "block_comment",
            "blocked_at_fmt",
            "extended_at_fmt",
            "extend_reason",
            "extend_months",
            "payments",
        ]

    def get_savings(self, obj):
        return fmt_money(obj.savings_total)

    def get_days_left(self, obj):
        if not obj.membership_end:
            return None
        delta = (obj.membership_end - timezone.now().date()).days
        return max(delta, 0)

    def get_progress_pct(self, obj):
        if not (obj.membership_start and obj.membership_end):
            return None
        total = (obj.membership_end - obj.membership_start).days
        if total <= 0:
            return 100
        done = (timezone.now().date() - obj.membership_start).days
        return round(min(max(done / total * 100, 0), 100))

    def get_next_payment(self, obj):
        if obj.is_blocked or not obj.membership_end:
            return None
        if obj.membership_end < timezone.now().date():
            return None
        return fmt_date(obj.membership_end)


# ---------------------------------------------------------------------------
# Businesses
# ---------------------------------------------------------------------------


class BusinessListSerializer(serializers.ModelSerializer):
    date = serializers.DateField(source="submitted_at", format="%d.%m.%Y", read_only=True)

    class Meta:
        model = Business
        fields = [
            "id",
            "business_code",
            "name",
            "category",
            "discount_percent",
            "phone",
            "region",
            "district",
            "status",
            "date",
        ]


class BusinessTransactionSerializer(serializers.ModelSerializer):
    original = serializers.SerializerMethodField()
    final = serializers.SerializerMethodField()
    when = serializers.SerializerMethodField()

    class Meta:
        model = BusinessTransaction
        fields = ["id", "member_name", "cashier", "original", "final", "status", "when"]

    def get_original(self, obj):
        return fmt_money(obj.original_amount)

    def get_final(self, obj):
        return fmt_money(obj.final_amount)

    def get_when(self, obj):
        today = timezone.now().date()
        local = timezone.localtime(obj.created_at)
        if local.date() == today:
            return f"Bugun, {local.strftime('%H:%M')}"
        return local.strftime("%d.%m.%Y, %H:%M")


class BusinessDetailSerializer(serializers.ModelSerializer):
    date = serializers.DateField(source="submitted_at", format="%d.%m.%Y", read_only=True)
    registered = serializers.DateField(source="registered_at", format="%d.%m.%Y", read_only=True)
    users_count = serializers.SerializerMethodField()
    transactions_paid = serializers.SerializerMethodField()
    active_days = serializers.SerializerMethodField()
    min_purchase_fmt = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = [
            "id",
            "business_code",
            "name",
            "category",
            "business_type",
            "stir",
            "owner",
            "description",
            "phone",
            "email",
            "instagram",
            "telegram",
            "website",
            "region",
            "district",
            "address",
            "latitude",
            "longitude",
            "work_days",
            "work_hours",
            "discount_percent",
            "min_purchase",
            "min_purchase_fmt",
            "discount_scope",
            "login",
            "password",
            "document_name",
            "document_size_kb",
            "status",
            "reject_reason",
            "block_reason",
            "date",
            "registered",
            "users_count",
            "transactions_paid",
            "active_days",
        ]
        # Biznes panel paroli admin uchun ko'rinadi: uni adminning o'zi
        # "Yangi biznes qo'shish" oynasida o'rnatadi va biznes egasiga
        # yetkazishi kerak. Bu endpoint faqat admin uchun ochiq
        # (IsAdminOperator), panelda esa parol yashirin turadi va faqat
        # "ko'rsatish" tugmasi bosilganda ochiladi.
        # DIQQAT: bu maydonni hech qachon ommaviy/mijoz endpointlariga
        # qo'shmang — BusinessApplication serializerida u write_only qoladi.

    def get_users_count(self, obj):
        return obj.transactions.values("member_name").distinct().count()

    def get_transactions_paid(self, obj):
        # Money users who used the discount actually paid (final amount, successful only).
        total = sum(
            int(t.final_amount)
            for t in obj.transactions.all()
            if t.status == TransactionStatus.SUCCESS
        )
        if total >= 1_000_000:
            return f"{total / 1_000_000:.1f}M so'm".replace(".0M", "M")
        return fmt_money(total)

    def get_active_days(self, obj):
        anchor = obj.registered_at or obj.submitted_at
        return max((timezone.now().date() - anchor).days, 0)

    def get_min_purchase_fmt(self, obj):
        return fmt_money(obj.min_purchase)


class BusinessWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            "name",
            "category",
            "business_type",
            "stir",
            "owner",
            "description",
            "phone",
            "email",
            "instagram",
            "telegram",
            "website",
            "region",
            "district",
            "address",
            "latitude",
            "longitude",
            "work_days",
            "work_hours",
            "discount_percent",
            "min_purchase",
            "discount_scope",
            "login",
            "password",
            "document_name",
            "document_size_kb",
            "registered_at",
        ]
        extra_kwargs = {f: {"required": False} for f in fields if f not in ("name", "owner", "category")}


# ---------------------------------------------------------------------------
# Applications (landing 'Arizalar')
# ---------------------------------------------------------------------------


class BusinessApplicationSerializer(serializers.ModelSerializer):
    when = serializers.SerializerMethodField()

    class Meta:
        model = BusinessApplication
        fields = ["id", "business_name", "category", "phone", "region", "discount_percent", "status", "when"]

    def get_when(self, obj):
        now = timezone.now()
        local = timezone.localtime(obj.created_at)
        if local.date() == now.date():
            return f"Bugun · {local.strftime('%H:%M')}"
        if (now.date() - local.date()).days == 1:
            return f"Kecha · {local.strftime('%H:%M')}"
        return local.strftime("%d.%m · %H:%M")


class LandingBusinessApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessApplication
        fields = [
            "business_name",
            "category",
            "phone",
            "region",
            "discount_percent",
            # Landing wizard'ining to'liq tafsiloti (ixtiyoriy maydonlar)
            "source_id",
            "responsible_name",
            "business_type",
            "description",
            "email",
            "instagram",
            "telegram",
            "website",
            "district",
            "address",
            "work_days",
            "work_hours",
            "min_purchase",
            "discount_scope",
            "login",
            "password",
            "latitude",
            "longitude",
        ]
        extra_kwargs = {
            f: {"required": False}
            for f in fields
            if f not in ("business_name", "category", "phone", "region")
        }


class BusinessApplicationDetailSerializer(serializers.ModelSerializer):
    """Ariza detail oynasi — landing'da kiritilgan barcha ma'lumotlar."""

    when = serializers.SerializerMethodField()
    date = serializers.DateTimeField(
        source="created_at", format="%d.%m.%Y %H:%M", read_only=True
    )
    min_purchase_fmt = serializers.SerializerMethodField()
    created_business_id = serializers.IntegerField(
        source="created_business.id", read_only=True, allow_null=True
    )

    class Meta:
        model = BusinessApplication
        fields = [
            "id",
            "business_name",
            "category",
            "phone",
            "region",
            "discount_percent",
            "status",
            "when",
            "date",
            "responsible_name",
            "business_type",
            "description",
            "email",
            "instagram",
            "telegram",
            "website",
            "district",
            "address",
            "work_days",
            "work_hours",
            "min_purchase",
            "min_purchase_fmt",
            "discount_scope",
            "login",
            "password",
            "latitude",
            "longitude",
            "reject_reason",
            "created_business_id",
        ]
        # Parol javobda HECH QACHON qaytmaydi — admin panel xodimlari biznes
        # egasining parolini ko'rmasligi kerak.
        extra_kwargs = {"password": {"write_only": True}}

    def get_when(self, obj):
        now = timezone.now()
        local = timezone.localtime(obj.created_at)
        if local.date() == now.date():
            return f"Bugun · {local.strftime('%H:%M')}"
        if (now.date() - local.date()).days == 1:
            return f"Kecha · {local.strftime('%H:%M')}"
        return local.strftime("%d.%m · %H:%M")

    def get_min_purchase_fmt(self, obj):
        return fmt_money(obj.min_purchase or 0)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


class PaymentListSerializer(serializers.ModelSerializer):
    amount_fmt = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source="created_at", format="%d.%m.%Y", read_only=True)

    class Meta:
        model = Payment
        fields = ["txn_id", "user_display_name", "amount_fmt", "method", "status", "date", "member_id"]

    def get_amount_fmt(self, obj):
        return fmt_money(obj.amount)


class PaymentDetailSerializer(serializers.ModelSerializer):
    amount_fmt = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source="created_at", format="%d.%m.%Y", read_only=True)
    period = serializers.SerializerMethodField()
    member_info = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "txn_id",
            "user_display_name",
            "amount_fmt",
            "months",
            "method",
            "status",
            "psp_ref",
            "period",
            "date",
            "refund_reason",
            "refund_comment",
            "member_id",
            "member_info",
            "history",
        ]

    def get_amount_fmt(self, obj):
        return fmt_money(obj.amount)

    def get_period(self, obj):
        if not (obj.period_start and obj.period_end):
            return None
        return f"{obj.period_start.strftime('%d.%m')} — {obj.period_end.strftime('%d.%m.%Y')}"

    def get_member_info(self, obj):
        m = obj.member
        if not m:
            return None
        total_paid = m.payments.count()
        next_payment = None
        if not m.is_blocked and m.membership_end and m.membership_end >= timezone.now().date():
            has_refund_of_latest = (
                m.payments.order_by("-created_at").first() or obj
            ).status == "Qaytarilgan"
            if not has_refund_of_latest:
                next_payment = fmt_date(m.membership_end)
        return {
            "id": m.id,
            "member_code": m.member_code,
            "status": f"{m.status} · {m.activity_status}",
            "payments_count": f"{total_paid} ta ({m.months_subscribed} oy)",
            "next_payment": next_payment,
            "savings": fmt_money(m.savings_total),
        }

    def get_history(self, obj):
        if not obj.member:
            return []
        return MemberPaymentSerializer(obj.member.payments.all()[:10], many=True).data


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class NotificationSerializer(serializers.ModelSerializer):
    audience_label = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()
    open_rate = serializers.SerializerMethodField()
    language_label = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "body",
            "audience_type",
            "audience_label",
            "category",
            "member_id",
            "language",
            "language_label",
            "send_time",
            "time_ago",
            "delivered",
            "opened",
            "open_rate",
        ]

    def get_audience_label(self, obj):
        if obj.audience_type == "category" and obj.category:
            return obj.category
        if obj.audience_type == "individual" and obj.member:
            return obj.member.name
        if obj.audience_type == "premium":
            return "Premium"
        return "Barchaga"

    def get_time_ago(self, obj):
        delta = timezone.now() - obj.sent_at
        minutes = int(delta.total_seconds() // 60)
        if minutes < 1:
            return "Hozirgina"
        if minutes < 60:
            return f"{minutes} daqiqa oldin"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} soat oldin"
        return f"{hours // 24} kun oldin"

    def get_open_rate(self, obj):
        if not obj.delivered:
            return None
        return f"{round(obj.opened / obj.delivered * 100)}%"

    def get_language_label(self, obj):
        return {"uz": "O'zbek", "ru": "Русский", "en": "English"}.get(obj.language, obj.language)


class NotificationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["title", "body", "audience_type", "category", "member", "language", "send_time"]


# ---------------------------------------------------------------------------
# Biznes so'rovlari (biznes panelidan)
# ---------------------------------------------------------------------------


class BusinessRequestSerializer(serializers.ModelSerializer):
    when = serializers.SerializerMethodField()

    class Meta:
        model = BusinessRequest
        fields = [
            "id",
            "kind",
            "title",
            "body",
            "old_percent",
            "new_percent",
            "reason",
            "status",
            "reject_reason",
            "when",
        ]

    def get_when(self, obj):
        local = timezone.localtime(obj.created_at)
        if local.date() == timezone.now().date():
            return f"Bugun · {local.strftime('%H:%M')}"
        return local.strftime("%d.%m.%Y · %H:%M")


class ReferralRequestSerializer(serializers.ModelSerializer):
    when = serializers.SerializerMethodField()

    class Meta:
        model = ReferralRequest
        fields = [
            "id",
            "member_name",
            "member_phone",
            "invited_count",
            "status",
            "reject_reason",
            "when",
        ]

    def get_when(self, obj):
        local = timezone.localtime(obj.created_at)
        if local.date() == timezone.now().date():
            return f"Bugun · {local.strftime('%H:%M')}"
        return local.strftime("%d.%m.%Y · %H:%M")


# ---------------------------------------------------------------------------
# Admin alerts (bell)
# ---------------------------------------------------------------------------


class AdminAlertSerializer(serializers.ModelSerializer):
    business_id = serializers.IntegerField(source="business.id", read_only=True, allow_null=True)
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = AdminAlert
        fields = ["id", "kind", "title", "body", "business_id", "time_ago", "is_read"]

    def get_time_ago(self, obj):
        delta = timezone.now() - obj.created_at
        minutes = int(delta.total_seconds() // 60)
        if minutes < 1:
            return "Hozirgina"
        if minutes < 60:
            return f"{minutes} daqiqa oldin"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} soat oldin"
        return f"{hours // 24} kun oldin"
