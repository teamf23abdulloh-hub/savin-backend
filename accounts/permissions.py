"""Admin paneli endpointlarini himoyalash.

Birlashtirilgandan keyin bitta DRF konfiguratsiyasi ikkala tizimga xizmat
qiladi, ya'ni mijozning JWT tokeni ham `IsAuthenticated`dan o'tadi. Admin panel
endpointlariga faqat `AdminUser` kira olishi uchun shu ruxsat sinfi kerak.
"""

from rest_framework.permissions import BasePermission

from .models import AdminUser


class IsAdminOperator(BasePermission):
    """Faqat admin panel operatori (AdminUser) uchun ruxsat.

    Mijoz / biznes egasi / kassir JWT tokeni bilan kelsa `request.user`
    `users.User` bo'ladi — bu yerda rad etiladi.
    """

    message = "Bu bo'lim faqat admin panel operatorlari uchun."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return isinstance(user, AdminUser) and user.is_active
