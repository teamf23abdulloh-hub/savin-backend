"""Mobil ilova foydalanuvchisi o'zgarganda admin paneldagi `Member` yangilanadi.

`core/sync.py` dagi izohga qarang — mobil ro'yxatdan o'tish `users.User`
yaratardi, lekin admin panel `core.Member` dan o'qigani uchun yangi
foydalanuvchilar ro'yxatda ko'rinmasdi.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import Membership, User

from .sync import sync_member_safe


@receiver(post_save, sender=User, dispatch_uid="core_sync_member_from_user")
def sync_member_on_user_save(sender, instance, **kwargs):
    """Mijoz ro'yxatdan o'tganda yoki ismi/blok holati o'zgarganda."""
    sync_member_safe(instance)


@receiver(post_save, sender=Membership, dispatch_uid="core_sync_member_from_membership")
def sync_member_on_membership_save(sender, instance, **kwargs):
    """Obuna holati o'zgarganda status ham yangilansin (Premium / Muddati o'tgan)."""
    if instance.user_id:
        sync_member_safe(instance.user)
