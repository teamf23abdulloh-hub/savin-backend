from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from businesses.models import Business
from users.models import User


class Transaction(models.Model):
    """
    Kassir tomonidan amalga oshirilgan savdo tranzaksiyalari
    Screenshot'dagi "Chegirralar tarixi" jadvalining ma'lumotlari
    """
    
    STATUS_CHOICES = [
        ('completed', 'Amalga oshirildi'),
        ('cancelled', 'Bekor qilindi'),
        ('refunded', 'Refund qilindi'),
    ]
    
    # Relationship
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='transactions'
    )
    cashier = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='transactions_created'
    )
    
    # Customer Information
    customer_name = models.CharField(
        max_length=200,
        verbose_name="Mijoz nomi"
    )
    customer_phone = models.CharField(
        max_length=20, 
        blank=True,
        verbose_name="Mijoz telefoni"
    )
    
    # Service/Product Information
    service_name = models.CharField(
        max_length=200,
        verbose_name="Xizmat nomi",
        help_text="Masalan: Soch olish, Soqul qilish, Soch + Soqul"
    )
    service_category = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name="Kategoriya"
    )
    
    # Pricing Information (Screenshot'dagi: Adi narx, To'lanagan)
    base_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Asl narx"
    )
    
    discount_percent = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Chegirma foizi (%)"
    )
    
    discount_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Chegirma miqdori"
    )
    
    final_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="To'lanagan narx"
    )
    
    # Status & Notes
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='completed',
        verbose_name="Holati"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Izohlar"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Yaratilgan vaqti"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Yangilangan vaqti"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', '-created_at']),
            models.Index(fields=['cashier', '-created_at']),
            models.Index(fields=['status']),
        ]
        verbose_name = "Tranzaksiya"
        verbose_name_plural = "Tranzaksiyalar"
    
    def save(self, *args, **kwargs):
        """Auto-calculate discount_amount va final_price"""
        if self.base_price and self.discount_percent:
            self.discount_amount = (self.base_price * self.discount_percent) / 100
            self.final_price = self.base_price - self.discount_amount
        else:
            self.discount_amount = 0
            self.final_price = self.base_price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.customer_name} - {self.service_name} ({self.created_at.date()})"


class TransactionLog(models.Model):
    """
    Tranzaksiya tarixini kuzatish (kim, qachon, nima o'zgargan)
    """
    ACTION_CHOICES = [
        ('created', 'Yaratildi'),
        ('updated', 'Yangilandi'),
        ('cancelled', 'Bekor qilindi'),
        ('refunded', 'Refund qilindi'),
    ]
    
    transaction = models.ForeignKey(
        Transaction, 
        on_delete=models.CASCADE, 
        related_name='logs'
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name="Harakat"
    )
    changed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="O'zgartirildi"
    )
    old_values = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Eski qiymatlar"
    )
    new_values = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Yangi qiymatlar"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Vaqti"
    )
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Tranzaksiya logi"
        verbose_name_plural = "Tranzaksiya logları"
    
    def __str__(self):
        return f"{self.transaction.id} - {self.action} ({self.timestamp})"


class DailyTransactionStat(models.Model):
    """
    Kunlik tranzaksiya statistikasi (dashboardga uchun)
    """
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE,
        related_name='daily_stats'
    )
    date = models.DateField(
        db_index=True,
        verbose_name="Sana"
    )
    
    # Stats
    total_transactions = models.IntegerField(
        default=0,
        verbose_name="Jami tranzaksiyalar"
    )
    total_base_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Jami asl narxi"
    )
    total_discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Jami chegirma"
    )
    total_final_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Jami to'lanagan"
    )
    average_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="O'rtacha chegirma %"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        ordering = ['-date']
        unique_together = ['business', 'date']
        verbose_name = "Kunlik statistika"
        verbose_name_plural = "Kunlik statistikalar"
        indexes = [
            models.Index(fields=['business', '-date']),
        ]
    
    def __str__(self):
        return f"{self.business.name} - {self.date}"