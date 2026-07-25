"""Admin panel operatorlari.

Ikkala backend birlashtirilgandan keyin `AUTH_USER_MODEL` — `users.User`
(mijoz / biznes egasi / kassir). Django'da AUTH_USER_MODEL faqat bitta bo'ladi,
shuning uchun `AdminUser` oddiy model bo'lib qoldi: u hamon `AbstractUser`dan
meros oladi (parol, `check_password`, `is_active` va h.k. o'zgarishsiz), lekin
`request.user`ga `accounts.authentication.AdminTokenAuthentication` orqali
tushadi — DRF'ning `rest_framework.authtoken` moduli o'rniga shu yerdagi
`AdminToken` ishlatiladi (uning `Token` modeli AUTH_USER_MODEL'ga bog'langan).
"""

import binascii
import os

from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models


class AdminUser(AbstractUser):
    """Single-tenant Savin admin operator account."""

    phone = models.CharField(max_length=32, blank=True)

    # `users.User` ham `AbstractUser`dan meros oladi va ikkalasi ham Group /
    # Permission'ga standart `related_name="user_set"` bilan bog'lanardi — bu
    # nomlar to'qnashuvi (fields.E304). Shuning uchun bu yerda alohida nom.
    groups = models.ManyToManyField(
        Group,
        verbose_name="groups",
        blank=True,
        related_name="admin_user_set",
        related_query_name="admin_user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name="user permissions",
        blank=True,
        related_name="admin_user_set",
        related_query_name="admin_user",
    )

    def __str__(self):
        return self.username


class AdminToken(models.Model):
    """`rest_framework.authtoken.Token` ning AdminUser uchun nusxasi.

    DRF'ning o'z Token modeli `settings.AUTH_USER_MODEL`ga (ya'ni `users.User`ga)
    bog'langani uchun admin operatorini saqlay olmaydi. Kalit formati va
    ishlatilishi bir xil: `Authorization: Token <key>`.
    """

    key = models.CharField("Key", max_length=40, primary_key=True)
    user = models.OneToOneField(
        AdminUser, related_name="auth_token", on_delete=models.CASCADE
    )
    created = models.DateTimeField("Created", auto_now_add=True)

    @classmethod
    def generate_key(cls):
        return binascii.hexlify(os.urandom(20)).decode()

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.key


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        AdminUser, on_delete=models.CASCADE, related_name="notification_prefs"
    )
    new_user = models.BooleanField(default=True)
    new_payment = models.BooleanField(default=True)
    new_business_application = models.BooleanField(default=True)
    weekly_report = models.BooleanField(default=False)

    def __str__(self):
        return f"Prefs<{self.user.username}>"


class Language(models.TextChoices):
    UZ = "uz", "O'zbek"
    RU = "ru", "Русский"
    EN = "en", "English"


class AccountSettings(models.Model):
    user = models.OneToOneField(AdminUser, on_delete=models.CASCADE, related_name="account_settings")
    two_factor_enabled = models.BooleanField(default=True)
    language = models.CharField(max_length=4, choices=Language.choices, default=Language.UZ)
    dark_mode = models.BooleanField(default=True)

    def __str__(self):
        return f"Settings<{self.user.username}>"
