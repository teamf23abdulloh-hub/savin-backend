from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import Membership, User, UserActivityLog
from users.permissions import IsAdminRole, IsSuperAdmin
from users.serializers import (
    AdminAccountCreateSerializer,
    AdminAccountSerializer,
    AdminUserDetailSerializer,
    AdminUserListSerializer,
    BlockUserSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    MembershipUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    """Ro'yxatdan o'tish (mijoz / biznes egasi)."""

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class LoginView(APIView):
    """Kirish (Login): Email + Parol, 2FA (ixtiyoriy)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = serializer.get_tokens(user)

        user.last_seen_at = timezone.now()
        user.save(update_fields=["last_seen_at"])
        UserActivityLog.objects.create(user=user, action="login")

        return Response(
            {"tokens": tokens, "user": UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )


class MeView(generics.RetrieveUpdateAPIView):
    """Profil / Sozlama: Biznes ma'lumotlari (foydalanuvchi o'zi uchun)."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response({"detail": "Eski parol noto'g'ri."}, status=400)
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"detail": "Parol muvaffaqiyatli o'zgartirildi."})


# ---------------- ADMIN PANEL: Foydalanuvchilar boshqaruvi ----------------


class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Ro'yxatni ko'rish (filter, qidirish) -> Foydalanuvchi tanlash -> Profilini ko'rish.
    """

    # Admin panelning "Foydalanuvchilar boshqaruvi" bo'limi faqat oddiy
    # foydalanuvchilarni (mijoz, biznes egasi, kassir) ko'rsatadi.
    # Admin/Superadmin akkauntlarini boshqarish alohida — SuperAdminAdminAccountViewSet.
    queryset = User.objects.exclude(role__in=[User.Role.ADMIN, User.Role.SUPERADMIN]).select_related("membership")
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["role", "is_blocked", "is_active"]
    search_fields = ["username", "email", "phone_number"]
    ordering_fields = ["created_at", "last_seen_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminUserDetailSerializer
        return AdminUserListSerializer


class AdminUserBlockView(APIView):
    """Bloklash / Blokni ochish."""

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        # Admin/Superadmin akkauntini faqat superadmin bloklay oladi.
        if user.role in (User.Role.ADMIN, User.Role.SUPERADMIN) and request.user.role != User.Role.SUPERADMIN:
            return Response(
                {"detail": "Admin akkauntlarini faqat superadmin bloklashi mumkin."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BlockUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.is_blocked = serializer.validated_data["is_blocked"]
        user.blocked_reason = serializer.validated_data.get("blocked_reason", "")
        user.save(update_fields=["is_blocked", "blocked_reason"])
        return Response(AdminUserDetailSerializer(user).data)


class AdminMembershipUpdateView(APIView):
    """Membership uzaytirish / bekor qilish."""

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        membership, _ = Membership.objects.get_or_create(user=user)
        serializer = MembershipUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]

        if action == "cancel":
            membership.status = Membership.Status.CANCELLED
        else:
            days = serializer.validated_data.get("days", 30)
            base = membership.expires_at if membership.expires_at and membership.expires_at > timezone.now() else timezone.now()
            membership.expires_at = base + timezone.timedelta(days=days)
            membership.status = Membership.Status.ACTIVE
        membership.save()
        return Response({"status": membership.status, "expires_at": membership.expires_at})


# ---------------- SUPERADMIN: Adminlarni boshqarish (1-rol) ----------------


class SuperAdminAdminAccountViewSet(viewsets.ModelViewSet):
    """
    Faqat SUPERADMIN foydalana oladi:
    - Admin akkauntlari ro'yxatini ko'rish (filter, qidirish)
    - Yangi admin akkaunt yaratish
    - Admin akkauntini yangilash / bloklash / o'chirish
    """

    queryset = User.objects.filter(role__in=[User.Role.ADMIN, User.Role.SUPERADMIN]).select_related("membership")
    permission_classes = [IsSuperAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["role", "is_blocked", "is_active"]
    search_fields = ["username", "email", "phone_number"]
    ordering_fields = ["created_at", "last_seen_at"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return AdminAccountCreateSerializer
        return AdminAccountSerializer

    def perform_destroy(self, instance):
        # Xavfsizlik uchun jismonan o'chirish o'rniga deaktivatsiya qilamiz.
        instance.is_active = False
        instance.is_blocked = True
        instance.blocked_reason = "Superadmin tomonidan o'chirilgan/deaktivatsiya qilingan."
        instance.save(update_fields=["is_active", "is_blocked", "blocked_reason"])
