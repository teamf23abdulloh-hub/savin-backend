import csv
import re
import uuid
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.models import Application, Business, Cashier
from discounts.models import Discount, DiscountChangeRequest, DiscountUsage
from discounts.serializers import (
    DiscountSerializer,
    CashierDashboardSerializer,
    DiscountChangeRequestCreateSerializer,
    DiscountChangeRequestSerializer,
    DiscountChangeReviewSerializer,
    DiscountStatSerializer,
    DiscountUsageCreateSerializer,
    DiscountUsageSerializer,
    QrScanSerializer,
)
from notifications.models import UserNotification
from users.models import User
from users.permissions import IsAdminRole, IsBusinessOwner, IsCashier


def filter_by_date_range(queryset, request, field="used_at"):
    """
    ?date_from=YYYY-MM-DD va ?date_to=YYYY-MM-DD parametrlari bo'yicha filtrlash.
    Noto'g'ri formatdagi qiymatlar (500 xato bermasligi uchun) e'tiborsiz qoldiriladi.
    """
    date_from = parse_date(request.query_params.get("date_from") or "")
    date_to = parse_date(request.query_params.get("date_to") or "")
    if date_from:
        queryset = queryset.filter(**{f"{field}__date__gte": date_from})
    if date_to:
        queryset = queryset.filter(**{f"{field}__date__lte": date_to})
    return queryset


# ==================== BIZNES EGASI: Chegirmalar ====================


class MyDiscountListCreateView(generics.ListCreateAPIView):
    """Biznesning chegirma turlari: ro'yxat / yangi qo'shish (biznes egasi)."""

    serializer_class = DiscountSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwner]
    pagination_class = None

    def _business(self):
        return get_object_or_404(Business, owner=self.request.user)

    def get_queryset(self):
        return Discount.objects.filter(business=self._business())

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["business"] = self._business()
        return ctx

    def perform_create(self, serializer):
        serializer.save(business=self._business())


class MyDiscountDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Chegirmani tahrirlash / o'chirish (biznes egasi)."""

    serializer_class = DiscountSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwner]

    def _business(self):
        return get_object_or_404(Business, owner=self.request.user)

    def get_queryset(self):
        return Discount.objects.filter(business=self._business())

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["business"] = self._business()
        return ctx


class MyDiscountToggleView(APIView):
    """Chegirmani faol/nofaol qilish (kartadagi tugmacha)."""

    permission_classes = [IsAuthenticated, IsBusinessOwner]

    def post(self, request, pk):
        business = get_object_or_404(Business, owner=request.user)
        discount = get_object_or_404(Discount, pk=pk, business=business)
        discount.is_active = not discount.is_active
        discount.save(update_fields=["is_active", "updated_at"])
        return Response(DiscountSerializer(discount).data)


class MyDiscountInfoView(APIView):
    """Chegirmalar -> Joriy foizlar ro'yxati."""

    permission_classes = [IsAuthenticated, IsBusinessOwner]

    def get(self, request):
        business = get_object_or_404(Business, owner=request.user)
        current_percent = business.application.discount_percent if business.application else None
        pending = DiscountChangeRequest.objects.filter(
            business=business, status=DiscountChangeRequest.Status.PENDING
        ).first()
        return Response(
            {
                "current_percent": current_percent,
                "pending_request": DiscountChangeRequestSerializer(pending).data if pending else None,
            }
        )


class DiscountChangeRequestCreateView(APIView):
    """Foiz o'zgartirish -> So'rov -> Admin."""

    permission_classes = [IsAuthenticated, IsBusinessOwner]

    def post(self, request):
        business = get_object_or_404(Business, owner=request.user)
        serializer = DiscountChangeRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Bir vaqtda faqat bitta ko'rib chiqilayotgan so'rov bo'lishi mumkin
        # (frontend ham shu qoidaga tayanadi: pending_request bo'lsa tugma bloklanadi).
        if DiscountChangeRequest.objects.filter(
            business=business, status=DiscountChangeRequest.Status.PENDING
        ).exists():
            return Response(
                {"detail": "Sizda allaqachon ko'rib chiqilayotgan so'rov mavjud."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_percent = business.application.discount_percent if business.application else 0
        change_request = DiscountChangeRequest.objects.create(
            business=business,
            requested_by=request.user,
            old_percent=old_percent,
            new_percent=serializer.validated_data["new_percent"],
            reason=serializer.validated_data.get("reason", ""),
        )

        # Admin panel qo'ng'irog'ida bildirishnoma chiqishi uchun so'rovni
        # admin panel backendiga uzatamiz (best-effort). Bildirishnoma
        # bosilganda o'sha biznesning detail sahifasi ochiladi.
        from businesses.integrations import notify_admin_panel_business_event

        reason = serializer.validated_data.get("reason", "")
        notify_admin_panel_business_event(
            business,
            title=f"{business.name}: chegirma foizini o'zgartirish so'rovi",
            body=(
                f"{old_percent}% dan {change_request.new_percent}% ga o'zgartirish so'raldi."
                + (f" Sabab: {reason}" if reason else "")
            ),
            # Admin panel "So'rovlar" bo'limida tasdiqlash/rad etish uchun
            # so'rovning o'zi ham uzatiladi (request_id bilan bridge qaytadi).
            extra={
                "kind": "discount_request",
                "request_id": str(change_request.id),
                "old_percent": old_percent,
                "new_percent": change_request.new_percent,
                "reason": reason,
            },
        )
        return Response(DiscountChangeRequestSerializer(change_request).data, status=status.HTTP_201_CREATED)


class DiscountHistoryView(generics.ListAPIView):
    """Chegirma tarixi: Kim keldi, qachon, qancha."""

    serializer_class = DiscountUsageSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwner]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["used_at"]
    # Frontend (Asosiy, Statistika, Chegirma tarixi sahifalari) to'liq ro'yxatni
    # olib, hisob-kitob va sahifalashni o'zi qiladi — shu sabab bu endpoint
    # sahifalanmaydi. Aks holda 20 tadan ortiq yozuvda statistika noto'g'ri chiqadi.
    pagination_class = None

    def get_queryset(self):
        business = get_object_or_404(Business, owner=self.request.user)
        queryset = DiscountUsage.objects.filter(business=business).select_related(
            "customer", "cashier"
        )
        # Avval date_from/date_to parametrlar qabul qilinmasdi (filterset yo'q edi),
        # frontend esa aynan shu filtrga tayanadi.
        return filter_by_date_range(queryset, self.request)


class DiscountHistoryExportView(APIView):
    """Filtr & Export: CSV, sana oralig'i."""

    permission_classes = [IsAuthenticated, IsBusinessOwner]

    def get(self, request):
        business = get_object_or_404(Business, owner=request.user)
        qs = filter_by_date_range(
            DiscountUsage.objects.filter(business=business).select_related(
                "customer", "cashier"
            ),
            request,
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="chegirma_tarixi_{business.id}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Mijoz", "Kassir", "Foiz", "Xarid summasi", "Chegirma summasi", "Sana"])
        for usage in qs:
            writer.writerow(
                [
                    usage.customer.email if usage.customer else "-",
                    usage.cashier.full_name if usage.cashier else "-",
                    usage.applied_percent,
                    usage.purchase_amount,
                    usage.discount_amount,
                    usage.used_at.strftime("%Y-%m-%d %H:%M"),
                ]
            )
        return response


class DiscountStatisticsView(APIView):
    """Statistika: Hafta/oy grafigi."""

    permission_classes = [IsAuthenticated, IsBusinessOwner]

    def get(self, request):
        business = get_object_or_404(Business, owner=request.user)
        period = request.query_params.get("period", "week")
        now = timezone.now()
        since = now - timezone.timedelta(days=7 if period == "week" else 30)

        qs = DiscountUsage.objects.filter(business=business, used_at__gte=since)
        data = {
            "period": period,
            "total_amount": qs.aggregate(s=Sum("discount_amount"))["s"] or 0,
            "total_transactions": qs.count(),
        }
        return Response(DiscountStatSerializer(data).data)


# ==================== KASSIR PANELI ====================

# Mijoz ilovasidagi QR ichidagi qiymat: "SAVIN-USER-<uuid>-<millisekund>".
# Eski/boshqa ko'rinishlar ham qabul qilinadi: toza UUID yoki email.
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)
# QR ilovada har 5 daqiqada yangilanadi. Telefon va server soati biroz farq
# qilishi mumkin, shuning uchun chegara kengroq olingan.
QR_MAX_AGE_SECONDS = 15 * 60


def find_customer_by_qr(qr_value):
    """QR qiymatidan mijozni topadi.

    Qaytaradi: `(customer, error)` — `error` bo'lsa foydalanuvchiga
    ko'rsatiladigan tushunarli matn.
    """
    value = (qr_value or "").strip()
    if not value:
        return None, "QR kod bo'sh."

    # 1) Ichidan UUID ajratib olamiz (prefiks/suffiks bo'lsa ham)
    match = _UUID_RE.search(value)
    if match:
        # QR eskirganini tekshiramiz (oxiridagi millisekundli vaqt belgisi)
        tail = value[match.end():].strip("-")
        if tail.isdigit():
            try:
                issued_ms = int(tail)
                age = timezone.now().timestamp() - issued_ms / 1000
                if age > QR_MAX_AGE_SECONDS:
                    return None, "QR kod muddati tugagan. Mijoz ilovada QR'ni yangilasin."
            except (ValueError, OverflowError):
                pass  # vaqt belgisi buzuq bo'lsa e'tiborsiz qoldiramiz
        customer = User.objects.filter(pk=match.group(0)).first()
        return customer, None

    # 2) Email ko'rinishida bo'lsa
    if "@" in value:
        return User.objects.filter(email__iexact=value).first(), None

    return None, None


def get_active_cashier_or_404(user):
    """So'rov yuborgan foydalanuvchining faol kassir profili."""
    return get_object_or_404(
        Cashier.objects.select_related("business", "business__application"),
        user=user,
        is_active=True,
    )


class CashierApplyDiscountView(APIView):
    """Kassir mijozga chegirma qo'llaydi (yangi tranzaksiya yozadi)."""

    permission_classes = [IsAuthenticated, IsCashier]

    def post(self, request):
        cashier = get_active_cashier_or_404(request.user)
        business = cashier.business
        serializer = DiscountUsageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = None
        customer_id = serializer.validated_data.get("customer_id")
        customer_email = serializer.validated_data.get("customer_email")
        if customer_id:
            # QR skanerlashdan kelgan mijoz ID'si
            customer = User.objects.filter(pk=customer_id).first()
            if not customer:
                return Response(
                    {"detail": "Mijoz topilmadi."}, status=status.HTTP_404_NOT_FOUND
                )
        elif customer_email:
            customer, _ = User.objects.get_or_create(
                email=customer_email, defaults={"username": customer_email, "role": User.Role.CUSTOMER}
            )

        application = business.application
        percent = application.discount_percent if application else 0
        purchase_amount = serializer.validated_data["purchase_amount"]

        # "Minimal xarid summasi" turidagi chegirmada limit tekshiriladi
        if (
            application
            and application.discount_type == Application.DiscountType.MIN_PURCHASE
            and application.min_purchase_amount
            and purchase_amount < application.min_purchase_amount
        ):
            return Response(
                {
                    "detail": (
                        f"Chegirma faqat {application.min_purchase_amount} so'mdan "
                        "yuqori xaridlarga qo'llaniladi."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        discount_amount = (purchase_amount * percent / Decimal(100)).quantize(
            Decimal("0.01")
        )

        usage = DiscountUsage.objects.create(
            business=business,
            customer=customer,
            cashier=cashier,
            applied_percent=percent,
            purchase_amount=purchase_amount,
            discount_amount=discount_amount,
        )

        # Biznes egasiga "Yangi mijoz" bildirishnomasi (Bildirishnomalar sahifasi uchun)
        UserNotification.objects.create(
            user=business.owner,
            notification_type=UserNotification.NotificationType.NEW_CUSTOMER,
            title="Yangi mijoz",
            body=(
                f"{cashier.full_name} {percent}% chegirma qo'lladi: "
                f"{purchase_amount} so'm xarid, {discount_amount} so'm chegirma."
            ),
        )

        return Response(DiscountUsageSerializer(usage).data, status=status.HTTP_201_CREATED)


class CashierMeView(APIView):
    """Kassir profili: o'z ma'lumotlari va biriktirilgan biznes."""

    permission_classes = [IsAuthenticated, IsCashier]

    def get(self, request):
        cashier = get_object_or_404(
            Cashier.objects.select_related(
                "business", "business__category", "business__application"
            ),
            user=request.user,
        )
        business = cashier.business
        return Response(
            {
                "id": cashier.id,
                "full_name": cashier.full_name,
                "email": request.user.email,
                "phone": cashier.phone,
                "login": cashier.login,
                # Panelda ko'rsatiladigan kassir raqami (UUID'ning oxirgi qismi)
                "cashier_code": f"#KSR-{str(cashier.id)[-4:].upper()}",
                "is_active": cashier.is_active,
                "added_at": cashier.added_at,
                "business": {
                    "id": business.id,
                    "name": business.name,
                    "category": business.category.name if business.category_id else None,
                    "phone_number": business.phone_number,
                    "full_address": business.full_address,
                    "current_percent": (
                        business.application.discount_percent
                        if business.application
                        else None
                    ),
                },
            }
        )

    def patch(self, request):
        """Kassir o'z ma'lumotlarini o'zgartiradi (ism, telefon, parol).

        Login, biznes va kassir ID o'zgarmaydi — ular tizim tomonidan
        biriktiriladi va kirish/hisobot yaxlitligiga bog'liq.
        """
        cashier = get_object_or_404(Cashier, user=request.user)
        user = request.user

        full_name = request.data.get("full_name")
        if full_name is not None:
            full_name = str(full_name).strip()
            if not full_name:
                return Response({"full_name": ["Ism bo'sh bo'lmasin."]}, status=400)
            cashier.full_name = full_name

        phone = request.data.get("phone")
        if phone is not None:
            cashier.phone = str(phone).strip()
            user.phone_number = cashier.phone or None
            user.save(update_fields=["phone_number"])

        password = request.data.get("password")
        if password:
            if len(str(password)) < 6:
                return Response(
                    {"password": ["Parol kamida 6 ta belgidan iborat bo'lsin."]},
                    status=400,
                )
            user.set_password(str(password))
            user.save(update_fields=["password"])
            # Biznes egasi panelida ko'rinadigan nusxa ham yangilanadi
            cashier.password_plain = str(password)

        cashier.save()
        return self.get(request)


class CashierDashboardView(APIView):
    """Kassir dashboard: bugungi tashriflar, chegirma va tushum."""

    permission_classes = [IsAuthenticated, IsCashier]

    def get(self, request):
        cashier = get_active_cashier_or_404(request.user)
        business = cashier.business
        today = timezone.localdate()

        today_usages = DiscountUsage.objects.filter(
            business=business, used_at__date=today
        )
        totals = today_usages.aggregate(
            discount=Sum("discount_amount"), purchase=Sum("purchase_amount")
        )
        discount_total = totals["discount"] or 0
        purchase_total = totals["purchase"] or 0

        data = {
            "today_visits": today_usages.count(),
            "my_today_visits": today_usages.filter(cashier=cashier).count(),
            "today_discount_amount": discount_total,
            "today_paid_amount": purchase_total - discount_total,
            "current_percent": (
                business.application.discount_percent if business.application else None
            ),
        }
        return Response(CashierDashboardSerializer(data).data)


class CashierVisitHistoryView(generics.ListAPIView):
    """Kassir paneli: Tashriflar tarixi (o'z biznesi bo'yicha).

    ?mine=1 — faqat shu kassir o'zi qo'llagan chegirmalar,
    ?date_from / ?date_to — sana oralig'i.
    """

    serializer_class = DiscountUsageSerializer
    permission_classes = [IsAuthenticated, IsCashier]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["used_at"]
    pagination_class = None

    def get_queryset(self):
        cashier = get_active_cashier_or_404(self.request.user)
        queryset = DiscountUsage.objects.filter(
            business=cashier.business
        ).select_related("customer", "cashier")
        if self.request.query_params.get("mine") in ("1", "true"):
            queryset = queryset.filter(cashier=cashier)
        return filter_by_date_range(queryset, self.request)


class CashierScanQrView(APIView):
    """QR skanerlash: mijoz QR kodi (mijoz ID yoki email) -> mijoz + joriy foiz.

    Kassir mijozning QR kodini skanerlaydi, backend mijozni topib qaytaradi;
    keyin kassir summa kiritib apply-discount'ga customer_id bilan yuboradi.
    """

    permission_classes = [IsAuthenticated, IsCashier]

    def post(self, request):
        cashier = get_active_cashier_or_404(request.user)
        serializer = QrScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        qr_value = serializer.validated_data["value"]

        customer, qr_error = find_customer_by_qr(qr_value)

        if qr_error:
            return Response({"detail": qr_error}, status=status.HTTP_400_BAD_REQUEST)
        if not customer:
            return Response(
                {"detail": "QR kod bo'yicha mijoz topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if customer.is_blocked:
            return Response(
                {"detail": "Bu mijoz bloklangan."}, status=status.HTTP_400_BAD_REQUEST
            )

        business = cashier.business
        percent = (
            business.application.discount_percent if business.application else 0
        )

        # Mijozning shu biznesdagi tashriflar tarixi
        usages = DiscountUsage.objects.filter(business=business, customer=customer)
        visits_count = usages.count()
        last_usage = usages.order_by("-used_at").first()
        if last_usage:
            days_ago = (timezone.localdate() - last_usage.used_at.date()).days
            last_visit_label = "Bugun" if days_ago == 0 else f"{days_ago} kun oldin"
        else:
            days_ago = None
            last_visit_label = "Birinchi tashrif"

        membership = getattr(customer, "membership", None)
        is_member_active = bool(membership and membership.status == "active")
        membership_type = "Savin a'zo" if is_member_active else "Oddiy mijoz"
        membership_status = (
            membership.get_status_display() if membership else "A'zolik yo'q"
        )

        full_name = (
            customer.get_full_name()
            or customer.username
            or customer.email.split("@")[0]
        )
        code = f"#{customer.id.hex[:8].upper()}"

        # Frontend'ning QR wizard'i kutadigan barcha maydonlar (StepMijoz,
        # StepTasdiqlash, StepMuvaffaqiyat komponentlari bilan mos).
        return Response(
            {
                "id": customer.id,
                "full_name": full_name,
                "email": customer.email,
                "phone_number": customer.phone_number,
                "membership_type": membership_type,
                "membership_status": membership_status,
                "status": membership_status,
                "code": code,
                "member_id": code,
                "visits_count": visits_count,
                "total_visits": visits_count,
                "last_visit_days_ago": days_ago,
                "last_visit_label": last_visit_label,
                "discount_percent": percent,
                # eski format bilan moslik uchun
                "customer": {
                    "id": customer.id,
                    "username": customer.username,
                    "email": customer.email,
                    "phone_number": customer.phone_number,
                },
                "current_percent": percent,
            }
        )


# ==================== ADMIN: Foiz o'zgartirish so'rovlarini boshqarish ====================


class AdminDiscountChangeRequestViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DiscountChangeRequest.objects.select_related("business", "requested_by").all()
    serializer_class = DiscountChangeRequestSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]


def apply_discount_review(change_request, action, reviewer=None, reject_reason=""):
    """Chegirma so'rovini tasdiqlash/rad etish — umumiy logika.

    Ikki joydan chaqiriladi: o'z admin API'miz (AdminDiscountChangeReviewView)
    va admin panel backendidan keladigan bridge (AdminBridgeDiscountReviewView).
    Ikkala holatda ham biznes egasiga (biznes panelning Bildirishnomalar
    bo'limiga) natija haqida bildirishnoma avtomatik yuboriladi.
    """
    change_request.reviewed_by = reviewer
    change_request.reviewed_at = timezone.now()

    if action == "approve":
        change_request.status = DiscountChangeRequest.Status.APPROVED
        business = change_request.business
        if business.application:
            business.application.discount_percent = change_request.new_percent
            business.application.save(update_fields=["discount_percent"])
        notif_title = "Chegirma so'rovi tasdiqlandi"
        notif_body = (
            f"Chegirma foizi {change_request.old_percent}% dan "
            f"{change_request.new_percent}% ga o'zgartirildi."
        )
    else:
        change_request.status = DiscountChangeRequest.Status.REJECTED
        notif_title = "Chegirma so'rovi rad etildi"
        notif_body = (
            f"{change_request.new_percent}% chegirma so'rovingiz admin "
            "tomonidan rad etildi."
            + (f" Sabab: {reject_reason}" if reject_reason else "")
        )

    change_request.save()

    # So'rov natijasi haqida biznes egasiga bildirishnoma
    UserNotification.objects.create(
        user=change_request.requested_by,
        notification_type=UserNotification.NotificationType.DISCOUNT,
        title=notif_title,
        body=notif_body,
    )
    return change_request


class AdminDiscountChangeReviewView(APIView):
    """Chegirma foizini o'zgartirish (Admin tomonidan)."""

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        change_request = get_object_or_404(DiscountChangeRequest, pk=pk)
        serializer = DiscountChangeReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        apply_discount_review(
            change_request,
            serializer.validated_data["action"],
            reviewer=request.user,
            reject_reason=request.data.get("reason", ""),
        )
        return Response(DiscountChangeRequestSerializer(change_request).data)


class AdminBridgeDiscountReviewView(APIView):
    """Admin panel backendi (alohida tizim) chegirma so'rovini tasdiqlab/rad
    etib bo'lgach, natijani shu yerga qaytaradi. Asosiy bazada so'rov holati
    yangilanadi va biznes egasiga bildirishnoma boradi (biznes panelning
    Bildirishnomalar bo'limi). Token bilan himoyalangan.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from django.conf import settings

        token = request.data.get("token") or ""
        expected = getattr(settings, "ADMIN_PANEL_BRIDGE_TOKEN", "")
        if not expected or token != expected:
            return Response(
                {"detail": "Noto'g'ri bridge token."},
                status=status.HTTP_403_FORBIDDEN,
            )

        change_request = get_object_or_404(
            DiscountChangeRequest, pk=request.data.get("request_id")
        )
        if change_request.status != DiscountChangeRequest.Status.PENDING:
            return Response(
                {"detail": "Bu so'rov allaqachon ko'rib chiqilgan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action = request.data.get("action")
        if action not in ("approve", "reject"):
            return Response(
                {"detail": "action approve yoki reject bo'lishi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        apply_discount_review(
            change_request,
            action,
            reject_reason=request.data.get("reason", ""),
        )
        return Response({"status": change_request.status})
