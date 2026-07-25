from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from analytics.models import DailyStatSnapshot
from businesses.models import Business
from discounts.models import DiscountUsage
from payments.models import Payment
from users.models import User, UserActivityLog


class Command(BaseCommand):
    help = "Kunlik statistika snapshotini hisoblab, DailyStatSnapshot jadvaliga yozadi (cron uchun)."

    def handle(self, *args, **options):
        today = timezone.localdate()
        now = timezone.now()

        day_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        month_start = day_start - timezone.timedelta(days=30)

        dau = UserActivityLog.objects.filter(created_at__date=today).values("user").distinct().count()
        mau = UserActivityLog.objects.filter(created_at__gte=month_start).values("user").distinct().count()

        new_users = User.objects.filter(created_at__date=today).count()
        new_businesses = Business.objects.filter(created_at__date=today).count()

        downloads_count = User.objects.filter(created_at__date=today).count()
        paid_count = Payment.objects.filter(created_at__date=today, status=Payment.Status.SUCCESS).count()
        conversion_rate = (paid_count / downloads_count * 100) if downloads_count else 0

        total_discount_amount = (
            DiscountUsage.objects.filter(used_at__date=today).aggregate(s=Sum("discount_amount"))["s"] or 0
        )

        churned_users = User.objects.filter(is_blocked=True, updated_at__date=today).count()
        churn_rate = (churned_users / mau * 100) if mau else 0

        snapshot, _ = DailyStatSnapshot.objects.update_or_create(
            date=today,
            defaults=dict(
                dau=dau,
                mau=mau,
                new_users=new_users,
                new_businesses=new_businesses,
                downloads_count=downloads_count,
                paid_count=paid_count,
                conversion_rate=conversion_rate,
                total_discount_amount=total_discount_amount,
                churned_users=churned_users,
                churn_rate=churn_rate,
            ),
        )

        self.stdout.write(self.style.SUCCESS(f"Statistika yozildi: {snapshot.date}"))
