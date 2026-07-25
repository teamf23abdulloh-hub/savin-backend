from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

# `APIView` `rest_framework`dan emas, `core.adminbase`dan — shu fayldagi
# view'lar faqat admin operatoriga ochiq bo'lishi uchun (core/adminbase.py).
from core.adminbase import APIView

from .models import AdminToken, AdminUser, NotificationPreference, AccountSettings
from .serializers import (
    AccountSettingsSerializer,
    AdminUserCreateSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    NotificationPreferenceSerializer,
)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        login = (request.data.get("login") or "").strip()
        password = request.data.get("password") or ""
        if not login or not password:
            return Response(
                {"detail": "Login va parolni kiriting."}, status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request, username=login, password=password)
        if user is None:
            return Response(
                {"detail": "Login yoki parol noto'g'ri."}, status=status.HTTP_400_BAD_REQUEST
            )
        if not user.is_active:
            return Response(
                {"detail": "Hisob faol emas."}, status=status.HTTP_403_FORBIDDEN
            )

        # `authenticate()` avval ModelBackend'ni sinaydi va `users.User`ni ham
        # qaytarishi mumkin (mijoz emaili login bilan mos kelib qolsa) — admin
        # panelga faqat AdminUser kira olsin.
        if not isinstance(user, AdminUser):
            return Response(
                {"detail": "Login yoki parol noto'g'ri."}, status=status.HTTP_400_BAD_REQUEST
            )

        token, _ = AdminToken.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": AdminUserSerializer(user).data}
        )


class LogoutView(APIView):
    def post(self, request):
        AdminToken.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(AdminUserSerializer(request.user).data)

    def patch(self, request):
        serializer = AdminUserUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminUserSerializer(request.user).data)


class ChangePasswordView(APIView):
    def post(self, request):
        current = request.data.get("current_password") or ""
        new = request.data.get("new_password") or ""
        user = request.user

        if not user.check_password(current):
            return Response(
                {"detail": "Joriy parol noto'g'ri."}, status=status.HTTP_400_BAD_REQUEST
            )
        if len(new) < 6:
            return Response(
                {"detail": "Yangi parol kamida 6 belgidan iborat bo'lishi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new)
        user.save(update_fields=["password"])

        # Rotate token so the old one is invalidated.
        AdminToken.objects.filter(user=user).delete()
        token = AdminToken.objects.create(user=user)
        return Response({"token": token.key})


class AdminListCreateView(APIView):
    """List existing admin operators, or create a new one."""

    def get(self, request):
        admins = AdminUser.objects.all().order_by("date_joined")
        return Response(AdminUserSerializer(admins, many=True).data)

    def post(self, request):
        serializer = AdminUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        NotificationPreference.objects.get_or_create(user=user)
        AccountSettings.objects.get_or_create(user=user)
        return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


class AdminDetailView(APIView):
    """Remove another admin operator (an admin cannot delete themselves)."""

    def delete(self, request, pk):
        if request.user.pk == pk:
            return Response(
                {"detail": "O'zingizni o'chira olmaysiz."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            admin = AdminUser.objects.get(pk=pk)
        except AdminUser.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        admin.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationPreferenceView(APIView):
    def get_object(self, user):
        prefs, _ = NotificationPreference.objects.get_or_create(user=user)
        return prefs

    def get(self, request):
        prefs = self.get_object(request.user)
        return Response(NotificationPreferenceSerializer(prefs).data)

    def patch(self, request):
        prefs = self.get_object(request.user)
        serializer = NotificationPreferenceSerializer(
            prefs, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AccountSettingsView(APIView):
    def get_object(self, user):
        settings_obj, _ = AccountSettings.objects.get_or_create(user=user)
        return settings_obj

    def get(self, request):
        return Response(AccountSettingsSerializer(self.get_object(request.user)).data)

    def patch(self, request):
        settings_obj = self.get_object(request.user)
        serializer = AccountSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
