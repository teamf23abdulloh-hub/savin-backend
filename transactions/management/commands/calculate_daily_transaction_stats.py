# transactions/management/commands/calculate_daily_transaction_stats.py

from django.core.management.base import BaseCommand
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from datetime import timedelta
from transactions.models import Transaction, DailyTransactionStat
from businesses.models import Business


class Command(BaseCommand):
    help = 'Kunlik tranzaksiya statistikasini hisoblash'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Oldingi nechta kunning statistikasini hisoblash (default: 1)'
        )
        
        parser.add_argument(
            '--date',
            type=str,
            help='Aniq sana (YYYY-MM-DD formatida). Masalan: 2026-07-12'
        )
    
    def handle(self, *args, **options):
        days = options.get('days', 1)
        date_str = options.get('date')
        
        if date_str:
            try:
                from datetime import datetime as dt
                target_date = dt.strptime(date_str, '%Y-%m-%d').date()
                dates_to_process = [target_date]
            except ValueError:
                self.stdout.write(self.style.ERROR('Sana formati xato (YYYY-MM-DD)'))
                return
        else:
            # Oldingi N kun uchun
            dates_to_process = [
                (timezone.now().date() - timedelta(days=i)) 
                for i in range(days, 0, -1)
            ]
        
        total_stats = 0
        
        for target_date in dates_to_process:
            for business in Business.objects.all():
                transactions = Transaction.objects.filter(
                    business=business,
                    created_at__date=target_date,
                    status='completed'
                )
                
                stats = transactions.aggregate(
                    total=Count('id'),
                    total_base=Sum('base_price'),
                    total_discount=Sum('discount_amount'),
                    total_final=Sum('final_price'),
                    avg_discount=Avg('discount_percent')
                )
                
                stat_obj, created = DailyTransactionStat.objects.update_or_create(
                    business=business,
                    date=target_date,
                    defaults={
                        'total_transactions': stats['total'] or 0,
                        'total_base_amount': stats['total_base'] or 0,
                        'total_discount_amount': stats['total_discount'] or 0,
                        'total_final_amount': stats['total_final'] or 0,
                        'average_discount_percent': stats['avg_discount'] or 0,
                    }
                )
                
                total_stats += 1
                
                action = 'Yaratildi' if created else 'Yangilandi'
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ {action}: {business.name} - {target_date} '
                        f'({stats["total"] or 0} tranzaksiya, {stats["total_final"] or 0} UZS)'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Jami {total_stats} ta statistika hisoblandi')
        )