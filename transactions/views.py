from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import PermissionDenied

from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from django.http import HttpResponse
from datetime import datetime, timedelta
import csv

from .models import Transaction, TransactionLog, DailyTransactionStat
from .serializers import (
    TransactionListSerializer,
    TransactionDetailSerializer,
    TransactionCreateUpdateSerializer,
    DailyTransactionStatSerializer,
    TransactionSummarySerializer,
    TransactionExportSerializer
)
from businesses.models import Business, Cashier


def get_user_business(user):
    """✅ FIX: User modelida `.business` maydoni umuman yo'q — avvalgi kod
    `user.business` deb yozib har doim AttributeError chiqarardi (bu esa
    aynan kassir/biznes-egasi uchun eng asosiy funksiya — tranzaksiya
    yaratish/ko'rish — ishlamasligiga sabab bo'lardi).
    Haqiqiy bog'lanish: Business.owner (biznes egasi uchun) va
    Cashier.user -> Cashier.business (kassir uchun).
    """
    if user.role == 'business_owner':
        return Business.objects.filter(owner=user).first()
    if user.role == 'cashier':
        cashier = Cashier.objects.filter(user=user, is_active=True).first()
        return cashier.business if cashier else None
    return None


class TransactionPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000


class TransactionViewSet(viewsets.ModelViewSet):
    """Tranzaksiya boshqaruvi"""
    
    serializer_class = TransactionListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = TransactionPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['customer_name', 'service_name', 'customer_phone']
    ordering_fields = ['created_at', 'final_price', 'discount_percent']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Foydalanuvchining biznesiga tegishli tranzaksiyalar"""
        user = self.request.user
        
        base = Transaction.objects.select_related("cashier__cashier_profile")

        if user.role == 'admin' or user.role == 'superadmin':
            # Adminlar barchani ko'radi
            queryset = base
        elif user.role in ('business_owner', 'cashier'):
            # Biznes egasi/kassir faqat o'z biznesiga tegishlisini ko'radi
            business = get_user_business(user)
            queryset = (
                base.filter(business=business)
                if business
                else Transaction.objects.none()
            )
        else:
            queryset = Transaction.objects.none()
        
        # Filtrlar
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TransactionDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return TransactionCreateUpdateSerializer
        return TransactionListSerializer
    
    def perform_create(self, serializer):
        """Yangi tranzaksiya yaratish"""
        user = self.request.user
        
        # Kassir o'z biznesiga tranzaksiya qo'shadi
        if user.role == 'cashier':
            business = get_user_business(user)
            if not business:
                raise PermissionDenied(
                    "Sizga hech qanday biznes biriktirilmagan yoki kassir profilingiz faol emas"
                )
            serializer.save(
                business=business,
                cashier=user,
                status='completed'
            )
            # Log yaratish
            transaction = serializer.instance
            TransactionLog.objects.create(
                transaction=transaction,
                action='created',
                changed_by=user,
                new_values={
                    'customer_name': transaction.customer_name,
                    'service_name': transaction.service_name,
                    'base_price': str(transaction.base_price),
                    'discount_percent': transaction.discount_percent,
                    'final_price': str(transaction.final_price)
                }
            )
        else:
            raise PermissionDenied("Faqat kassirlar tranzaksiya yarata oladi")
    
    def perform_update(self, serializer):
        """Tranzaksiyani tahrirlash"""
        old_instance = self.get_object()
        old_values = {
            'base_price': str(old_instance.base_price),
            'discount_percent': old_instance.discount_percent,
        }
        
        instance = serializer.save()
        
        new_values = {
            'base_price': str(instance.base_price),
            'discount_percent': instance.discount_percent,
        }
        
        # Log yaratish
        TransactionLog.objects.create(
            transaction=instance,
            action='updated',
            changed_by=self.request.user,
            old_values=old_values,
            new_values=new_values
        )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Tranzaksiyani bekor qilish"""
        transaction = self.get_object()
        
        if transaction.status == 'cancelled':
            return Response(
                {'detail': 'Bu tranzaksiya allaqachon bekor qilingan'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        transaction.status = 'cancelled'
        transaction.save()
        
        # Log
        TransactionLog.objects.create(
            transaction=transaction,
            action='cancelled',
            changed_by=request.user
        )
        
        return Response(
            {'detail': 'Tranzaksiya bekor qilindi'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        """Tranzaksiyada refund qilish"""
        transaction = self.get_object()
        
        if transaction.status == 'refunded':
            return Response(
                {'detail': 'Bu tranzaksiya allaqachon refund qilingan'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        transaction.status = 'refunded'
        transaction.save()
        
        # Log
        TransactionLog.objects.create(
            transaction=transaction,
            action='refunded',
            changed_by=request.user,
            new_values={'refund_requested_by': request.user.get_full_name()}
        )
        
        return Response(
            {'detail': 'Refund qilingan'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Tranzaksiya xulosa (dashboard uchun)"""
        queryset = self.get_queryset()
        
        # Filtrlar
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if not date_from:
            date_from = (timezone.now() - timedelta(days=30)).date()
        if not date_to:
            date_to = timezone.now().date()
        
        queryset = queryset.filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
            status='completed'
        )
        
        stats = queryset.aggregate(
            total_transactions=Count('id'),
            total_amount=Sum('base_price'),
            total_discount=Sum('discount_amount'),
            total_final=Sum('final_price'),
            average_discount=Avg('discount_percent')
        )
        
        data = {
            'total_transactions': stats['total_transactions'] or 0,
            'total_amount': stats['total_amount'] or 0,
            'total_discount': stats['total_discount'] or 0,
            'total_final': stats['total_final'] or 0,
            'average_discount_percent': stats['average_discount'] or 0,
            'date_from': str(date_from),
            'date_to': str(date_to)
        }
        
        serializer = TransactionSummarySerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Satuq statistikasi (hafta/oy bo'yicha)"""
        queryset = self.get_queryset().filter(status='completed')
        period = request.query_params.get('period', 'week')  # week, month
        
        if period == 'month':
            days = 30
        else:
            days = 7
        
        data = []
        for i in range(days, -1, -1):
            date = timezone.now().date() - timedelta(days=i)
            day_data = queryset.filter(created_at__date=date).aggregate(
                count=Count('id'),
                total=Sum('final_price'),
                discount=Sum('discount_amount')
            )
            
            data.append({
                'date': str(date),
                'day_name': date.strftime('%a'),
                'transactions': day_data['count'] or 0,
                'total': day_data['total'] or 0,
                'discount': day_data['discount'] or 0
            })
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """CSV export"""
        queryset = self.get_queryset()
        
        # Filtrlar
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        # CSV yaratish
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Mijoz', 'Telefon', 'Xizmat', 'Asl narx', 
            'Chegirma %', 'Chegirma miqdori', 'To\'lanagan', 
            'Kassir', 'Holati', 'Sana'
        ])
        
        serializer = TransactionExportSerializer(queryset, many=True)
        for item in serializer.data:
            writer.writerow([
                item['id'],
                item['customer_name'],
                item['customer_phone'],
                item['service_name'],
                item['base_price'],
                item['discount_percent'],
                item['discount_amount'],
                item['final_price'],
                item['cashier_name'],
                item['status_display'],
                item['created_at']
            ])
        
        return response
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Bugun qilingan tranzaksiyalar"""
        today = timezone.now().date()
        queryset = self.get_queryset().filter(
            created_at__date=today,
            status='completed'
        )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class DailyStatViewSet(viewsets.ReadOnlyModelViewSet):
    """Kunlik statistika ko'rish (admin uchun)"""
    
    serializer_class = DailyTransactionStatSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date']
    ordering = ['-date']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'admin' or user.role == 'superadmin':
            return DailyTransactionStat.objects.all()
        elif user.role == 'business_owner':
            business = get_user_business(user)
            return (
                DailyTransactionStat.objects.filter(business=business)
                if business
                else DailyTransactionStat.objects.none()
            )
        else:
            return DailyTransactionStat.objects.none()
    
    @action(detail=False, methods=['get'])
    def generate(self, request):
        """Kunlik statistikani hisoblash (cron uchun)"""
        if request.user.role not in ['admin', 'superadmin']:
            raise PermissionDenied("Faqat admin")
        
        yesterday = timezone.now().date() - timedelta(days=1)
        
        for business in Business.objects.all():
            transactions = Transaction.objects.filter(
                business=business,
                created_at__date=yesterday,
                status='completed'
            )
            
            stats = transactions.aggregate(
                total=Count('id'),
                total_base=Sum('base_price'),
                total_discount=Sum('discount_amount'),
                total_final=Sum('final_price'),
                avg_discount=Avg('discount_percent')
            )
            
            DailyTransactionStat.objects.update_or_create(
                business=business,
                date=yesterday,
                defaults={
                    'total_transactions': stats['total'] or 0,
                    'total_base_amount': stats['total_base'] or 0,
                    'total_discount_amount': stats['total_discount'] or 0,
                    'total_final_amount': stats['total_final'] or 0,
                    'average_discount_percent': stats['avg_discount'] or 0,
                }
            )
        
        return Response(
            {'detail': f'{yesterday} uchun statistika hisoblandi'},
            status=status.HTTP_200_OK
        )