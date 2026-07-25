from rest_framework import serializers
from datetime import datetime, timedelta
from django.db.models import Sum, Avg, Count
from .models import Transaction, TransactionLog, DailyTransactionStat
from users.serializers import UserBasicSerializer


class TransactionLogSerializer(serializers.ModelSerializer):
    changed_by_detail = UserBasicSerializer(
        source='changed_by', 
        read_only=True
    )
    
    class Meta:
        model = TransactionLog
        fields = [
            'id', 'action', 'changed_by', 'changed_by_detail',
            'old_values', 'new_values', 'timestamp'
        ]
        read_only_fields = ['timestamp']


def resolve_cashier_name(user):
    """✅ FIX: kassirning haqiqiy ismi `Cashier.full_name` maydonida saqlanadi,
    avvalgi `cashier.get_full_name` esa User'ning bo'sh first/last_name'iga
    qaragani uchun doim "" qaytarardi (frontend jadvalida kassir ko'rinmasdi)."""
    if not user:
        return ""
    profile = getattr(user, "cashier_profile", None)
    if profile and profile.full_name:
        return profile.full_name
    return user.get_full_name() or user.username


class TransactionListSerializer(serializers.ModelSerializer):
    """Tranzaksiya ro'yxati uchun (jadval ko'rsatish)"""
    cashier_name = serializers.SerializerMethodField()

    def get_cashier_name(self, obj):
        return resolve_cashier_name(obj.cashier)

    class Meta:
        model = Transaction
        fields = [
            'id',
            'customer_name',
            'customer_phone',
            'service_name',
            'service_category',
            'base_price',
            'discount_percent',
            'discount_amount',
            'final_price',
            'cashier',
            'cashier_name',
            'status',
            'created_at'
        ]


class TransactionDetailSerializer(serializers.ModelSerializer):
    """Tranzaksiyaning to'liq ma'lumoti"""
    cashier_detail = UserBasicSerializer(
        source='cashier', 
        read_only=True
    )
    logs = TransactionLogSerializer(
        many=True, 
        read_only=True
    )
    
    class Meta:
        model = Transaction
        fields = [
            'id',
            'business',
            'customer_name',
            'customer_phone',
            'service_name',
            'service_category',
            'base_price',
            'discount_percent',
            'discount_amount',
            'final_price',
            'cashier',
            'cashier_detail',
            'status',
            'notes',
            'logs',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'discount_amount', 'final_price', 
            'created_at', 'updated_at'
        ]


class TransactionCreateUpdateSerializer(serializers.ModelSerializer):
    """Yangi tranzaksiya yaratish/tahrirlash"""
    
    class Meta:
        model = Transaction
        fields = [
            'id',
            'customer_name',
            'customer_phone',
            'service_name',
            'service_category',
            'base_price',
            'discount_percent',
            'discount_amount',
            'final_price',
            'status',
            'created_at',
            'notes'
        ]
        # ✅ FIX: avval bu maydonlar hech qayerda e'lon qilinmagani uchun
        # ModelSerializer ularni umuman qabul qilmas/qaytarmas edi — kassir
        # tranzaksiya yaratganda javobda ID, hisoblangan summa va status
        # kelmay, front-end "Muvaffaqiyatli" ekranini yoki keyingi
        # cancel/refund amalini amalga oshira olmasdi.
        read_only_fields = [
            'id', 'discount_amount', 'final_price', 'status', 'created_at',
        ]
    
    def validate_base_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Narx 0 dan katta bo'lishi kerak")
        return value
    
    def validate_discount_percent(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError("Chegirma 0-100% oralig'ida bo'lishi kerak")
        return value


class DailyTransactionStatSerializer(serializers.ModelSerializer):
    """Kunlik statistika"""
    
    class Meta:
        model = DailyTransactionStat
        fields = [
            'date',
            'total_transactions',
            'total_base_amount',
            'total_discount_amount',
            'total_final_amount',
            'average_discount_percent'
        ]


class TransactionSummarySerializer(serializers.Serializer):
    """Tranzaksiya xulosa (dashboard uchun)"""
    total_transactions = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_discount = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_final = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    date_range = serializers.SerializerMethodField()
    
    def get_date_range(self, obj):
        return {
            'from': obj.get('date_from'),
            'to': obj.get('date_to')
        }


class TransactionExportSerializer(serializers.ModelSerializer):
    """CSV export uchun"""
    cashier_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )

    def get_cashier_name(self, obj):
        return resolve_cashier_name(obj.cashier)
    
    class Meta:
        model = Transaction
        fields = [
            'id',
            'customer_name',
            'customer_phone',
            'service_name',
            'service_category',
            'base_price',
            'discount_percent',
            'discount_amount',
            'final_price',
            'cashier_name',
            'status',
            'status_display',
            'created_at'
        ]