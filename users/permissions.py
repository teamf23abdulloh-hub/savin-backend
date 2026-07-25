from rest_framework.permissions import BasePermission

from users.models import User


class IsAdminRole(BasePermission):
    """Faqat Admin/SuperAdmin."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.ADMIN, User.Role.SUPERADMIN)
        )


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == User.Role.SUPERADMIN
        )


class IsBusinessOwner(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == User.Role.BUSINESS_OWNER
        )


class IsCashier(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == User.Role.CASHIER
        )


class IsBusinessOwnerOrCashier(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.BUSINESS_OWNER, User.Role.CASHIER)
        )


class IsOwnerOfObject(BasePermission):
    """Object-level: request.user obyektning egasi bo'lishi kerak (owner/user maydoni orqali)."""

    owner_field = "owner"

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, self.owner_field, None)
        return owner == request.user
