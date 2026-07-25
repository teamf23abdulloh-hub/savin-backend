from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.models import Business
from notifications.models import PushNotification, UserNotification
from notifications.serializers import (
    PushNotificationCreateSerializer,
    PushNotificationSerializer,
    UserNotificationSerializer,
)
from users.models import User
from users.permissions import IsAdminRole


# ==================== FOYDALANUVCHI: bildirishnomalar oynasi ====================


class MyNotificationsView(generics.ListAPIView):
    """Bildirishnomalar: Yangi mijoz, chegirma, eslatma."""

    serializer_class = UserNotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_read", "notification_type"]
    # Frontend to'liq ro'yxatni oladi va o'zi ko'rsatadi (sahifalash tugmasi yo'q)
    pagination_class = None

    def get_queryset(self):
        return UserNotification.objects.filter(user=self.request.user)


class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notif = get_object_or_404(UserNotification, pk=pk, user=request.user)
        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return Response(UserNotificationSerializer(notif).data)


class MarkAllNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        UserNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"detail": "Barcha bildirishnomalar o'qilgan deb belgilandi."})


# ==================== ADMIN: Push bildirishnomalar ====================


def _dispatch_push_notification(push: PushNotification):
    """Push xabarni tegishli foydalanuvchilarga UserNotification sifatida yetkazish."""

    title = push.title_uz
    body = push.body_uz

    if push.audience == PushNotification.Audience.SINGLE_USER:
        targets = [push.target_user] if push.target_user else []
    elif push.audience == PushNotification.Audience.CATEGORY:
        owner_ids = Business.objects.filter(category=push.target_category).values_list("owner_id", flat=True)
        targets = list(User.objects.filter(id__in=owner_ids))
    else:  # ALL
        targets = list(User.objects.filter(is_active=True))

    UserNotification.objects.bulk_create(
        [
            UserNotification(
                user=u,
                push_notification=push,
                notification_type=UserNotification.NotificationType.SYSTEM,
                title=title,
                body=body,
            )
            for u in targets
        ]
    )
    push.status = PushNotification.Status.SENT
    push.sent_at = timezone.now()
    push.save(update_fields=["status", "sent_at"])


class AdminPushNotificationViewSet(viewsets.ModelViewSet):
    """
    Qabul qiluvchi tanlash -> Xabar yozish (UZ/RU/EN) -> Yuborish / Rejalashtirilgan yuborish
    """

    queryset = PushNotification.objects.all()
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["audience", "status"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PushNotificationCreateSerializer
        return PushNotificationSerializer


class AdminPushNotificationSendView(APIView):
    """Darhol yuborish."""

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        push = get_object_or_404(PushNotification, pk=pk)
        if push.status == PushNotification.Status.SENT:
            return Response({"detail": "Allaqachon yuborilgan."}, status=400)
        _dispatch_push_notification(push)
        return Response(PushNotificationSerializer(push).data)
