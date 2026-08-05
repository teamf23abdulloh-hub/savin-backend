from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum, Avg, Count
from .models import Transaction, DailyTransactionStat


@receiver(post_save, sender=Transaction)
def update_daily_stats(sender, instance, created, **kwargs):
    """
    Har safar tranzaksiya yaratilganda yoki yangilanganda 
    kunlik statistikani update qilish
    """
    if instance.status != 'completed':
        return
    
    date = instance.created_at.date()
    
    # Ushbu kun uchun jami statistika hisoblash
    daily_transactions = Transaction.objects.filter(
        business=instance.business,
        created_at__date=date,
        status='completed'
    )
    
    stats = daily_transactions.aggregate(
        total=Count('id'),
        total_base=Sum('base_price'),
        total_discount=Sum('discount_amount'),
        total_final=Sum('final_price'),
        avg_discount=Avg('discount_percent')
    )
    
    # Update yoki create qilish
    DailyTransactionStat.objects.update_or_create(
        business=instance.business,
        date=date,
        defaults={
            'total_transactions': stats['total'] or 0,
            'total_base_amount': stats['total_base'] or 0,
            'total_discount_amount': stats['total_discount'] or 0,
            'total_final_amount': stats['total_final'] or 0,
            'average_discount_percent': stats['avg_discount'] or 0,
        }
    )


@receiver(post_save, sender=Transaction)
def notify_customer_about_discount(sender, instance, created, **kwargs):
    """Kassir chegirma qo'llaganda mijozga ilovada bildirishnoma chiqadi.

    Dizayndagi "Chegirma qo'llanildi! — 17 500 so'm tejagansiz" xabari
    shu yerdan tug'iladi. Faqat mijoz hisobiga bog'langan tranzaksiyalar
    uchun (kassir QR/4 xonali kod orqali mijozni aniqlagan bo'lsa).
    """
    if not created or instance.status != 'completed' or not instance.customer_id:
        return

    from mobileapi.models import CustomerNotification

    saved = int(instance.discount_amount or 0)
    business_name = instance.business.name if instance.business_id else "Savin hamkori"
    CustomerNotification.objects.create(
        user_id=instance.customer_id,
        title="Chegirma qo'llanildi!",
        body=f"{business_name}da {saved:,} so'm tejagansiz.".replace(",", " "),
        kind=CustomerNotification.Kind.DISCOUNT,
    )