import calendar
import random
from datetime import timedelta

from django.db.models import Count, Max, Min, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# DIQQAT: `APIView`/`generics` ataylab `rest_framework`dan emas, `adminbase`dan
# olinadi — shu fayldagi barcha view'lar faqat admin operatoriga ochiq bo'lishi
# va admin panelning o'z sahifalashini saqlab qolishi uchun. Batafsil:
# core/adminbase.py.
from .adminbase import APIView, generics

from .models import (
    ActivityStatus,
    AdminAlert,
    AdminAlertKind,
    ApplicationStatus,
    AudienceType,
    Business,
    BusinessApplication,
    BusinessCategory,
    BusinessRequest,
    BusinessRequestStatus,
    ReferralRequest,
    ReferralRequestStatus,
    BusinessStatus,
    BusinessTransaction,
    ChurnReason,
    DailyActivity,
    Member,
    Notification,
    Payment,
    PaymentMethod,
    PaymentStatus,
    PlatformStat,
    Status,
    TransactionStatus,
)
from .bridge import notify_main_backend, review_discount_on_main, review_referral_on_main
from .inbox import (
    receive_business_application,
    receive_business_event,
    receive_referral_request,
)
from .serializers import (
    AdminAlertSerializer,
    BusinessApplicationDetailSerializer,
    BusinessApplicationSerializer,
    BusinessDetailSerializer,
    BusinessRequestSerializer,
    ReferralRequestSerializer,
    BusinessListSerializer,
    BusinessTransactionSerializer,
    BusinessWriteSerializer,
    MemberDetailSerializer,
    MemberListSerializer,
    NotificationCreateSerializer,
    NotificationSerializer,
    PaymentDetailSerializer,
    PaymentListSerializer,
)

PLAN_PRICES = {1: 20000, 3: 60000, 6: 120000}

MONTH_LABELS_UZ = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]
WEEKDAY_LABELS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]


def fmt_compact(value):
    value = int(value)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M so'm".replace(".0M", "M")
    if value >= 1000:
        return f"{value:,} so'm"
    return f"{value} so'm"


def parse_date(value):
    if not value:
        return None
    try:
        return timezone.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def add_months(date, months):
    """Shift a date by N calendar months, clamping the day (dateutil-free)."""
    month_index = date.month - 1 + months
    year = date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(date.day, calendar.monthrange(year, month)[1])
    return date.replace(year=year, month=month, day=day)


# ---------------------------------------------------------------------------
# Users (Foydalanuvchilar)
# ---------------------------------------------------------------------------


class MemberListView(generics.ListAPIView):
    serializer_class = MemberListSerializer

    def get_queryset(self):
        qs = Member.objects.all()
        p = self.request.query_params
        search = p.get("search")
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(phone__icontains=search)
                | Q(member_code__icontains=search)
            )
        status_param = p.get("status")
        if status_param == "Bloklangan":
            qs = qs.filter(is_blocked=True)
        elif status_param:
            qs = qs.filter(status=status_param, is_blocked=False)
        activity = p.get("activity")
        if activity:
            qs = qs.filter(activity_status=activity)
        savings_min = p.get("savings_min")
        if savings_min:
            qs = qs.filter(savings_total__gte=savings_min)
        savings_max = p.get("savings_max")
        if savings_max:
            qs = qs.filter(savings_total__lte=savings_max)
        return qs


class MemberDetailView(generics.RetrieveAPIView):
    queryset = Member.objects.all()
    serializer_class = MemberDetailSerializer


class MemberBlockView(APIView):
    """Block / unblock a member with a reason (design: 'Foydalanuvchini bloklash')."""

    def post(self, request, pk):
        try:
            member = Member.objects.get(pk=pk)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        blocked = request.data.get("blocked")
        blocked = (not member.is_blocked) if blocked is None else bool(blocked)
        member.is_blocked = blocked
        if blocked:
            member.block_reason = request.data.get("reason", "")
            member.block_comment = request.data.get("comment", "")
            member.blocked_at = timezone.now().date()
            member.activity_status = ActivityStatus.INACTIVE
        else:
            member.block_reason = ""
            member.block_comment = ""
            member.blocked_at = None
            member.activity_status = ActivityStatus.ACTIVE
        member.save()
        return Response(MemberDetailSerializer(member).data)


class MemberExtendView(APIView):
    """Extend a membership by 1/3/6 months (design: 'Obunani uzaytirish')."""

    def post(self, request, pk):
        try:
            member = Member.objects.get(pk=pk)
        except Member.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            months = int(request.data.get("months", 0))
        except (TypeError, ValueError):
            months = 0
        if months not in (1, 3, 6):
            return Response({"detail": "Muddat 1, 3 yoki 6 oy bo'lishi kerak"}, status=400)

        reason = request.data.get("reason", "Admin qarori")
        today = timezone.now().date()
        base = member.membership_end if member.membership_end and member.membership_end > today else today
        member.membership_end = add_months(base, months)
        if not member.membership_start:
            member.membership_start = today
        member.months_subscribed += months
        member.extended_at = today
        member.extend_reason = reason
        member.extend_months = months
        if member.status != Status.PREMIUM:
            member.status = Status.PREMIUM
        if "Referal" in reason:
            member.referral_invited = min(member.referral_invited + 1, member.referral_target)
        member.save()
        return Response(MemberDetailSerializer(member).data)


class MemberStatsView(APIView):
    def get(self, request):
        qs = Member.objects.all()
        month_start = timezone.now().date().replace(day=1)
        return Response(
            {
                "total": qs.count(),
                "premium": qs.filter(status=Status.PREMIUM).count(),
                "overdue": qs.filter(status=Status.OVERDUE).count(),
                "new_this_month": qs.filter(joined_at__gte=month_start).count(),
                "blocked": qs.filter(is_blocked=True).count(),
            }
        )


class MemberExportView(APIView):
    """JSON payload the frontend turns into a branded PDF report."""

    MAX_ROWS = 2000

    def get(self, request):
        qs = Member.objects.all()
        rows = [
            [
                m.member_code,
                m.name,
                m.phone,
                "Bloklangan" if m.is_blocked else m.status,
                m.joined_at.strftime("%d.%m.%Y"),
                f"{int(m.savings_total):,} so'm",
                m.activity_status,
            ]
            for m in qs[: self.MAX_ROWS]
        ]
        return Response(
            {
                "title": "Foydalanuvchilar ro'yxati",
                "columns": ["ID", "Ism", "Telefon", "A'zolik holati", "A'zo bo'lgan", "Jamg'arma", "Status"],
                "rows": rows,
                "total": qs.count(),
            }
        )


# ---------------------------------------------------------------------------
# Businesses (Bizneslar)
# ---------------------------------------------------------------------------


class BusinessListCreateView(generics.ListCreateAPIView):
    def get_serializer_class(self):
        if self.request.method == "POST":
            return BusinessWriteSerializer
        return BusinessListSerializer

    def get_queryset(self):
        qs = Business.objects.all()
        p = self.request.query_params
        search = p.get("search")
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(owner__icontains=search)
                | Q(business_code__icontains=search)
                | Q(phone__icontains=search)
            )
        status_param = p.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        categories = p.get("categories")
        if categories:
            qs = qs.filter(category__in=[c for c in categories.split(",") if c])
        region = p.get("region")
        if region:
            qs = qs.filter(region=region)
        discount_min = p.get("discount_min")
        if discount_min:
            qs = qs.filter(discount_percent__gte=discount_min)
        discount_max = p.get("discount_max")
        if discount_max:
            qs = qs.filter(discount_percent__lte=discount_max)
        return qs

    def perform_create(self, serializer):
        business = serializer.save(
            business_code=str(random.randint(200000000, 299999999)),
            status=BusinessStatus.PENDING,
            submitted_at=timezone.now().date(),
        )
        AdminAlert.objects.create(
            kind=AdminAlertKind.BUSINESS_APPLICATION,
            title="Yangi biznes qo'shildi",
            body=f"{business.name} admin tomonidan yaratildi — tasdiqlash kutilmoqda",
            business=business,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        detail = BusinessDetailSerializer(serializer.instance)
        return Response(detail.data, status=status.HTTP_201_CREATED)


class BusinessDetailView(generics.RetrieveUpdateAPIView):
    queryset = Business.objects.all()

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return BusinessWriteSerializer
        return BusinessDetailSerializer

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        return Response(BusinessDetailSerializer(self.get_object()).data)


class BusinessApproveView(APIView):
    """Approve a pending business (design: 'Tasdiqlash')."""

    def post(self, request, pk):
        try:
            business = Business.objects.get(pk=pk)
        except Business.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        business.status = BusinessStatus.APPROVED
        business.reject_reason = ""
        if not business.registered_at:
            business.registered_at = timezone.now().date()
        business.save()
        AdminAlert.objects.create(
            kind=AdminAlertKind.BUSINESS_APPROVED,
            title=f"{business.name} tasdiqlandi",
            body="Biznes listingi ilovada faollashdi",
            business=business,
        )
        return Response(BusinessDetailSerializer(business).data)


class BusinessRejectView(APIView):
    """Reject a pending business with a reason (design: 'Arizani rad etish')."""

    def post(self, request, pk):
        try:
            business = Business.objects.get(pk=pk)
        except Business.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "Rad etish sababi majburiy"}, status=400)
        business.status = BusinessStatus.REJECTED
        business.reject_reason = reason
        business.save()
        return Response(BusinessDetailSerializer(business).data)


class BusinessBlockView(APIView):
    """Block / unblock a partner business (design: 'Bloklash' on business profile)."""

    def post(self, request, pk):
        try:
            business = Business.objects.get(pk=pk)
        except Business.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if business.status == BusinessStatus.BLOCKED:
            business.status = BusinessStatus.APPROVED
            business.block_reason = ""
        else:
            business.status = BusinessStatus.BLOCKED
            business.block_reason = request.data.get("reason", "")
        business.save()
        return Response(BusinessDetailSerializer(business).data)


class BusinessTransactionsView(generics.ListAPIView):
    serializer_class = BusinessTransactionSerializer
    pagination_class = None

    def get_queryset(self):
        qs = BusinessTransaction.objects.filter(business_id=self.kwargs["pk"])
        p = self.request.query_params
        status_param = p.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        search = p.get("search")
        if search:
            qs = qs.filter(Q(member_name__icontains=search) | Q(cashier__icontains=search))
        return qs[:50]


class BusinessStatsView(APIView):
    def get(self, request):
        qs = Business.objects.all()
        return Response(
            {
                "total": qs.count(),
                "approved": qs.filter(status=BusinessStatus.APPROVED).count(),
                "pending": qs.filter(status__in=[BusinessStatus.PENDING, BusinessStatus.REPEAT]).count(),
                "blocked": qs.filter(status=BusinessStatus.BLOCKED).count(),
            }
        )


class BusinessExportView(APIView):
    """JSON payload the frontend turns into a branded PDF report."""

    MAX_ROWS = 2000

    def get(self, request):
        qs = Business.objects.all()
        rows = [
            [
                b.business_code,
                b.name,
                b.category,
                f"{b.discount_percent}%",
                b.phone,
                f"{b.region}, {b.district}",
                b.status,
                b.submitted_at.strftime("%d.%m.%Y"),
            ]
            for b in qs[: self.MAX_ROWS]
        ]
        return Response(
            {
                "title": "Hamkor bizneslar ro'yxati",
                "columns": ["ID", "Biznes nomi", "Kategoriya", "Chegirma", "Telefon", "Manzil", "Holat", "Sana"],
                "rows": rows,
                "total": qs.count(),
            }
        )


# ---------------------------------------------------------------------------
# Biznes so'rovlari (biznes panelidan kelgan, masalan chegirma o'zgartirish)
# ---------------------------------------------------------------------------


class BusinessRequestListView(generics.ListAPIView):
    """Biznes detail sahifasining "So'rovlar" bo'limi uchun ro'yxat."""

    serializer_class = BusinessRequestSerializer
    pagination_class = None

    def get_queryset(self):
        return BusinessRequest.objects.filter(business_id=self.kwargs["pk"])


class BusinessRequestApproveView(APIView):
    """So'rovni tasdiqlash. Natija asosiy backendga qaytariladi — u yerda
    foiz yangilanadi va biznes egasiga bildirishnoma boradi."""

    def post(self, request, pk):
        try:
            req = BusinessRequest.objects.get(pk=pk)
        except BusinessRequest.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if req.status != BusinessRequestStatus.PENDING:
            return Response(
                {"detail": "Bu so'rov allaqachon ko'rib chiqilgan."}, status=400
            )

        req.status = BusinessRequestStatus.APPROVED
        req.reviewed_at = timezone.now()
        req.save(update_fields=["status", "reviewed_at"])

        # Admin-tomondagi biznes kartasida ham foizni yangilab qo'yamiz
        if req.new_percent:
            req.business.discount_percent = req.new_percent
            req.business.save(update_fields=["discount_percent"])

        # Asosiy backend: so'rov holati + biznes egasiga bildirishnoma
        review_discount_on_main(req.source_id, "approve")

        return Response(BusinessRequestSerializer(req).data)


class BusinessRequestRejectView(APIView):
    """So'rovni rad etish (sabab majburiy). Sabab biznes egasiga
    bildirishnomada yetkaziladi."""

    def post(self, request, pk):
        try:
            req = BusinessRequest.objects.get(pk=pk)
        except BusinessRequest.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if req.status != BusinessRequestStatus.PENDING:
            return Response(
                {"detail": "Bu so'rov allaqachon ko'rib chiqilgan."}, status=400
            )
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "Rad etish sababi majburiy"}, status=400)

        req.status = BusinessRequestStatus.REJECTED
        req.reject_reason = reason
        req.reviewed_at = timezone.now()
        req.save(update_fields=["status", "reject_reason", "reviewed_at"])

        review_discount_on_main(req.source_id, "reject", reason=reason)

        return Response(BusinessRequestSerializer(req).data)


# ---------------------------------------------------------------------------
# Landing applications (Arizalar)
# ---------------------------------------------------------------------------


class ApplicationListView(generics.ListAPIView):
    serializer_class = BusinessApplicationSerializer

    def get_queryset(self):
        qs = BusinessApplication.objects.all()
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        base = BusinessApplication.objects.all()
        response.data["counts"] = {
            "all": base.count(),
            "new": base.filter(status=ApplicationStatus.NEW).count(),
            "reviewing": base.filter(status=ApplicationStatus.REVIEWING).count(),
            "contacted": base.filter(status=ApplicationStatus.CONTACTED).count(),
        }
        return response


class ApplicationUpdateView(APIView):
    def get(self, request, pk):
        """Ariza detail oynasi — landing'da kiritilgan barcha ma'lumotlar."""
        try:
            app = BusinessApplication.objects.get(pk=pk)
        except BusinessApplication.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(BusinessApplicationDetailSerializer(app).data)

    def patch(self, request, pk):
        try:
            app = BusinessApplication.objects.get(pk=pk)
        except BusinessApplication.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        new_status = request.data.get("status")
        if new_status not in ApplicationStatus.values:
            return Response({"detail": "Noto'g'ri holat"}, status=400)
        app.status = new_status
        app.save(update_fields=["status"])
        return Response(BusinessApplicationSerializer(app).data)


# Landing'dan keladigan business_type yorlig'ini admin paneldagi
# BusinessType qiymatiga o'girish ("MCHJ" -> "MChJ" va h.k.)
_BUSINESS_TYPE_MAP = {"yatt": "YaTT", "mchj": "MChJ", "ok": "OK"}


class ApplicationApproveView(APIView):
    """Arizani tasdiqlash: status 'Tasdiqlangan' + Bizneslar ro'yxatiga qo'shish.

    Natija asosiy backendga ham (reverse bridge) uzatiladi — u yerda biznes
    egasi hisobi (arizadagi login/parol bilan) va Business yoziladi.
    """

    def post(self, request, pk):
        try:
            app = BusinessApplication.objects.get(pk=pk)
        except BusinessApplication.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if app.status == ApplicationStatus.APPROVED and app.created_business_id:
            return Response(
                {"detail": "Bu ariza allaqachon tasdiqlangan."}, status=400
            )

        business = app.created_business
        if business is None:
            business = Business.objects.create(
                business_code=str(random.randint(200000000, 299999999)),
                name=app.business_name,
                category=app.category,
                business_type=_BUSINESS_TYPE_MAP.get(
                    (app.business_type or "").strip().lower(), "YaTT"
                ),
                owner=app.responsible_name or app.business_name,
                description=app.description,
                phone=app.phone,
                email=app.email,
                instagram=app.instagram,
                telegram=app.telegram,
                website=app.website,
                region=app.region,
                district=app.district,
                address=app.address,
                latitude=app.latitude,
                longitude=app.longitude,
                work_days=app.work_days or "Dushanba – Juma",
                work_hours=app.work_hours or "09:00 - 18:00",
                discount_percent=app.discount_percent,
                min_purchase=app.min_purchase or 0,
                discount_scope=app.discount_scope or "Barcha mahsulotlar",
                login=app.login,
                password=app.password,
                status=BusinessStatus.APPROVED,
                submitted_at=timezone.localtime(app.created_at).date(),
                registered_at=timezone.now().date(),
            )

        app.status = ApplicationStatus.APPROVED
        app.reject_reason = ""
        app.created_business = business
        app.save(update_fields=["status", "reject_reason", "created_business"])

        AdminAlert.objects.create(
            kind=AdminAlertKind.BUSINESS_APPROVED,
            title=f"{app.business_name} arizasi tasdiqlandi",
            body="Biznes 'Bizneslar' ro'yxatiga qo'shildi",
            business=business,
        )

        # Asosiy backendда ham tasdiqlash (biznes egasi hisobini yaratadi)
        notify_main_backend(app, "approve")

        return Response(BusinessApplicationDetailSerializer(app).data)


class ApplicationRejectView(APIView):
    """Arizani rad etish (sabab majburiy)."""

    def post(self, request, pk):
        try:
            app = BusinessApplication.objects.get(pk=pk)
        except BusinessApplication.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "Rad etish sababi majburiy"}, status=400)

        app.status = ApplicationStatus.REJECTED
        app.reject_reason = reason
        app.save(update_fields=["status", "reject_reason"])

        # Asosiy backendда ham rad etish (ariza egasiga bildirishnoma boradi)
        notify_main_backend(app, "reject", reason=reason)

        return Response(BusinessApplicationDetailSerializer(app).data)


class BusinessEventNotifyView(APIView):
    """Asosiy backend (savin_django) biznes panelidagi hodisalarni shu yerga
    uzatadi — masalan, biznes egasi chegirma foizini o'zgartirish so'rovi
    yuborganda. Natijada admin panel qo'ng'irog'ida (bell) bildirishnoma
    chiqadi; bildirishnoma bosilganda o'sha biznes detail sahifasi ochiladi.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            alert, business = receive_business_event(request.data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(
            {"id": alert.id, "business_id": business.id if business else None},
            status=status.HTTP_201_CREATED,
        )


class ReferralRequestReceiveView(APIView):
    """Public: asosiy backend (savin_django) mijozning referal mukofot
    so'rovini shu yerga uzatadi. Natijada admin panel qo'ng'irog'ida (bell)
    bildirishnoma chiqadi va "Referal so'rovlari" bo'limida ko'rinadi."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            req = receive_referral_request(request.data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"id": req.id}, status=status.HTTP_201_CREATED)


class ReferralRequestListView(generics.ListAPIView):
    """Admin: referal mukofot so'rovlari ro'yxati."""

    serializer_class = ReferralRequestSerializer

    def get_queryset(self):
        qs = ReferralRequest.objects.all()
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class MemberReferralRequestsView(generics.ListAPIView):
    """Admin: bitta foydalanuvchining referal so'rovlari (uning detail
    sahifasidagi 'So'rovlar' bo'limi uchun)."""

    serializer_class = ReferralRequestSerializer

    def get_queryset(self):
        return ReferralRequest.objects.filter(member_id=self.kwargs["pk"])


class ReferralRequestApproveView(APIView):
    """Admin: so'rovni tasdiqlash — mijoz a'zoligi +1 oyga uzayadi (asosiy
    backendда) va mijozga bildirishnoma boradi."""

    def post(self, request, pk):
        try:
            req = ReferralRequest.objects.get(pk=pk)
        except ReferralRequest.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if req.status != ReferralRequestStatus.PENDING:
            return Response({"detail": "Bu so'rov allaqachon ko'rib chiqilgan."}, status=400)

        req.status = ReferralRequestStatus.APPROVED
        req.reviewed_at = timezone.now()
        req.save(update_fields=["status", "reviewed_at"])

        # Admin-tomondagi Member kartasini ham yangilaymiz (ko'rinish uchun):
        # a'zolik +1 oy, Premium holat, va referal hisoblagichi 0 ga qaytadi
        # (mukofot berildi — yangi tsikl boshlanadi, "3/3" -> "0/3").
        if req.member_id:
            m = req.member
            today = timezone.now().date()
            base = m.membership_end if m.membership_end and m.membership_end > today else today
            m.membership_end = base + timezone.timedelta(days=30)
            m.months_subscribed = (m.months_subscribed or 0) + 1
            m.status = Status.PREMIUM
            m.extended_at = today
            m.extend_reason = "Referal mukofoti (3 do'st)"
            m.extend_months = 1
            m.referral_invited = 0  # mukofot berildi — hisoblagich nolga qaytadi
            m.save()

        review_referral_on_main(req.source_id, "approve")
        return Response(ReferralRequestSerializer(req).data)


class ReferralRequestRejectView(APIView):
    """Admin: so'rovni rad etish (sabab majburiy). Sabab mijozga bildirishnomada
    yetkaziladi."""

    def post(self, request, pk):
        try:
            req = ReferralRequest.objects.get(pk=pk)
        except ReferralRequest.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if req.status != ReferralRequestStatus.PENDING:
            return Response({"detail": "Bu so'rov allaqachon ko'rib chiqilgan."}, status=400)
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "Rad etish sababi majburiy"}, status=400)

        req.status = ReferralRequestStatus.REJECTED
        req.reject_reason = reason
        req.reviewed_at = timezone.now()
        req.save(update_fields=["status", "reject_reason", "reviewed_at"])
        review_referral_on_main(req.source_id, "reject", reason=reason)
        return Response(ReferralRequestSerializer(req).data)


class LandingBusinessApplyView(APIView):
    """Public endpoint the landing website posts new partnership applications to."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        app = receive_business_application(request.data)
        return Response(BusinessApplicationSerializer(app).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Payments (To'lovlar)
# ---------------------------------------------------------------------------


class PaymentListView(generics.ListAPIView):
    serializer_class = PaymentListSerializer

    def get_queryset(self):
        qs = Payment.objects.all()
        p = self.request.query_params
        search = p.get("search")
        if search:
            qs = qs.filter(Q(txn_id__icontains=search) | Q(user_display_name__icontains=search))
        status_param = p.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        method_param = p.get("method")
        if method_param:
            qs = qs.filter(method=method_param)
        start = parse_date(p.get("start"))
        if start:
            qs = qs.filter(created_at__date__gte=start)
        end = parse_date(p.get("end"))
        if end:
            qs = qs.filter(created_at__date__lte=end)
        return qs


class PaymentDetailView(generics.RetrieveAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentDetailSerializer
    lookup_field = "txn_id"
    lookup_url_kwarg = "txn_id"


class PaymentRefundView(APIView):
    """Refund a payment (design: 'Qaytarishni tasdiqlang')."""

    def post(self, request, txn_id):
        try:
            payment = Payment.objects.get(txn_id=txn_id)
        except Payment.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if payment.status == PaymentStatus.REFUNDED:
            return Response({"detail": "Bu to'lov allaqachon qaytarilgan"}, status=400)

        payment.status = PaymentStatus.REFUNDED
        payment.refund_reason = request.data.get("reason", "Foydalanuvchi so'rovi")
        payment.refund_comment = request.data.get("comment", "")
        payment.refunded_at = timezone.now()
        payment.save()

        # Membership is cancelled together with the refund (design: 'Bekor qilinadi')
        member = payment.member
        if member:
            member.membership_end = timezone.now().date()
            member.activity_status = ActivityStatus.INACTIVE
            member.save(update_fields=["membership_end", "activity_status"])

        return Response(PaymentDetailSerializer(payment).data)


class PaymentStatsView(APIView):
    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

        success = Payment.objects.filter(status=PaymentStatus.SUCCESS)
        this_month = success.filter(created_at__date__gte=month_start).aggregate(t=Sum("amount"))["t"] or 0
        last_month = (
            success.filter(created_at__date__gte=prev_month_start, created_at__date__lt=month_start).aggregate(
                t=Sum("amount")
            )["t"]
            or 0
        )
        refunds = Payment.objects.filter(status=PaymentStatus.REFUNDED)
        refund_sum = refunds.aggregate(t=Sum("amount"))["t"] or 0

        return Response(
            {
                "this_month": f"{int(this_month):,} so'm",
                "last_month": f"{int(last_month):,}",
                "total_count": f"{Payment.objects.count():,}",
                "refund_count": refunds.count(),
                "refund_sum": f"{int(refund_sum):,} so'm",
            }
        )


class PaymentChartsView(APIView):
    """Monthly revenue bars + payment-method share donut."""

    def get(self, request):
        today = timezone.now().date()
        start = parse_date(request.query_params.get("start"))
        end = parse_date(request.query_params.get("end"))

        month_anchor = today.replace(day=1)
        monthly = []
        for i in range(5, -1, -1):
            m_start = add_months(month_anchor, -i)
            m_end = add_months(m_start, 1)
            month_qs = Payment.objects.filter(
                status=PaymentStatus.SUCCESS, created_at__date__gte=m_start, created_at__date__lt=m_end
            )
            total = month_qs.aggregate(t=Sum("amount"))["t"] or 0
            by_method = {
                method: int(
                    month_qs.filter(method=method).aggregate(t=Sum("amount"))["t"] or 0
                )
                for method in PaymentMethod.values
            }
            monthly.append(
                {
                    "month": MONTH_LABELS_UZ[m_start.month - 1],
                    "value": int(total),
                    "by_method": by_method,
                }
            )

        donut_qs = Payment.objects.filter(status=PaymentStatus.SUCCESS)
        if start:
            donut_qs = donut_qs.filter(created_at__date__gte=start)
        if end:
            donut_qs = donut_qs.filter(created_at__date__lte=end)
        donut_total = donut_qs.aggregate(t=Sum("amount"))["t"] or 0
        methods = []
        for method in PaymentMethod.values:
            amount = donut_qs.filter(method=method).aggregate(t=Sum("amount"))["t"] or 0
            pct = round(amount / donut_total * 100) if donut_total else 0
            methods.append({"method": method, "pct": pct, "amount": int(amount)})

        return Response({"monthly": monthly, "methods": methods})


class PaymentExportView(APIView):
    """JSON payload the frontend turns into a branded PDF report."""

    MAX_ROWS = 2000

    def get(self, request):
        qs = Payment.objects.all()
        rows = [
            [
                p.txn_id,
                p.user_display_name,
                f"{int(p.amount):,} so'm",
                p.method,
                p.created_at.strftime("%d.%m.%Y %H:%M"),
                p.status,
            ]
            for p in qs[: self.MAX_ROWS]
        ]
        return Response(
            {
                "title": "To'lovlar tarixi",
                "columns": ["TXN-ID", "Foydalanuvchi", "Summa", "To'lov usuli", "Sana", "Holat"],
                "rows": rows,
                "total": qs.count(),
            }
        )


# ---------------------------------------------------------------------------
# Notifications (Bildirishnomalar)
# ---------------------------------------------------------------------------


def audience_size(audience_type, category=None, member=None):
    if audience_type == AudienceType.PREMIUM:
        return Member.objects.filter(status=Status.PREMIUM).count()
    if audience_type == AudienceType.CATEGORY:
        # everyone who visited that category at least once
        return (
            Member.objects.filter(visits__business__category=category).distinct().count()
            or Member.objects.count()
        )
    if audience_type == AudienceType.INDIVIDUAL:
        return 1 if member else 0
    return Member.objects.count()


class NotificationListCreateView(generics.ListCreateAPIView):
    queryset = Notification.objects.all()
    pagination_class = None

    def get_serializer_class(self):
        if self.request.method == "POST":
            return NotificationCreateSerializer
        return NotificationSerializer

    def perform_create(self, serializer):
        data = serializer.validated_data
        delivered = audience_size(
            data.get("audience_type"), data.get("category"), data.get("member")
        )
        opened = int(delivered * random.uniform(0.55, 0.8))
        instance = serializer.save(delivered=delivered, opened=opened)
        AdminAlert.objects.create(
            kind=AdminAlertKind.PUSH_SENT,
            title=f"Push xabar {delivered:,} ga yuborildi".replace(",", " "),
            body=instance.title,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            NotificationSerializer(serializer.instance).data, status=status.HTTP_201_CREATED
        )


class NotificationDeleteView(generics.DestroyAPIView):
    queryset = Notification.objects.all()


class NotificationMetaView(APIView):
    """Audience sizes + selectable categories for the composer."""

    def get(self, request):
        return Response(
            {
                "all_count": Member.objects.count(),
                "premium_count": Member.objects.filter(status=Status.PREMIUM).count(),
                "categories": list(BusinessCategory.values),
            }
        )


# ---------------------------------------------------------------------------
# Admin alerts (dashboard bell)
# ---------------------------------------------------------------------------


class AdminAlertListView(generics.ListAPIView):
    serializer_class = AdminAlertSerializer
    pagination_class = None

    def get_queryset(self):
        return AdminAlert.objects.all()[:20]

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = {
            "results": response.data,
            "unread_count": AdminAlert.objects.filter(is_read=False).count(),
        }
        return response


class AdminAlertMarkReadView(APIView):
    def post(self, request, pk=None):
        if pk is None:
            AdminAlert.objects.filter(is_read=False).update(is_read=True)
        else:
            AdminAlert.objects.filter(pk=pk).update(is_read=True)
        return Response({"unread_count": AdminAlert.objects.filter(is_read=False).count()})


# ---------------------------------------------------------------------------
# Dashboard (Bosh sahifa)
# ---------------------------------------------------------------------------


class DashboardView(APIView):
    def get(self, request):
        today = timezone.now().date()

        start_param = request.query_params.get("start")
        end_param = request.query_params.get("end")
        end_date = parse_date(end_param) or today
        start_date = parse_date(start_param) or (end_date - timedelta(days=6))
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        range_given = bool(start_param and end_param)

        month_start = end_date.replace(day=1)

        active_users = Member.objects.exclude(status=Status.OVERDUE).exclude(is_blocked=True).count()
        active_businesses = Business.objects.filter(status=BusinessStatus.APPROVED).count()

        revenue_qs = Payment.objects.filter(status=PaymentStatus.SUCCESS)
        if range_given:
            monthly_revenue = (
                revenue_qs.filter(
                    created_at__date__gte=start_date, created_at__date__lte=end_date
                ).aggregate(total=Sum("amount"))["total"]
                or 0
            )
        else:
            monthly_revenue = (
                revenue_qs.filter(created_at__date__gte=month_start).aggregate(total=Sum("amount"))["total"]
                or 0
            )

        stat = PlatformStat.objects.first()
        downloads = stat.downloads if stat else 0
        total_members = Member.objects.count()
        subscribed = Member.objects.filter(status=Status.PREMIUM).count()
        subscription_rate = f"{(subscribed / downloads * 100):.1f}%" if downloads else "0%"

        span_days = (end_date - start_date).days + 1
        if range_given and 1 <= span_days <= 31:
            day_range = [start_date + timedelta(days=i) for i in range(span_days)]
        else:
            day_range = [end_date - timedelta(days=i) for i in range(6, -1, -1)]

        activity_by_date = {
            a.date: a for a in DailyActivity.objects.filter(date__in=day_range)
        }
        weekly = []
        for day in day_range:
            new_members = Member.objects.filter(joined_at=day).count()
            act = activity_by_date.get(day)
            weekly.append(
                {
                    "day": WEEKDAY_LABELS[day.weekday()],
                    "date": day.strftime("%d.%m.%Y"),
                    "value": act.daily_active if act else new_members,
                    "total_visits": act.qr_scans if act else 0,
                    "new_members": new_members,
                    "active_members": act.daily_active if act else 0,
                }
            )

        monthly = []
        prev_revenue = None
        for i in range(5, -1, -1):
            m_start = add_months(month_start, -i)
            m_end = add_months(m_start, 1)
            month_payments = Payment.objects.filter(
                status=PaymentStatus.SUCCESS, created_at__date__gte=m_start, created_at__date__lt=m_end
            )
            revenue = month_payments.aggregate(total=Sum("amount"))["total"] or 0
            if prev_revenue:
                growth_pct = f"{'+' if revenue >= prev_revenue else ''}{((revenue - prev_revenue) / prev_revenue * 100):.0f}%"
            else:
                growth_pct = "—"
            monthly.append(
                {
                    "month": MONTH_LABELS_UZ[m_start.month - 1],
                    "year": m_start.year,
                    "value": int(revenue),
                    "payment_count": month_payments.count(),
                    "growth_pct": growth_pct,
                }
            )
            prev_revenue = revenue

        members_qs = Member.objects.all()
        if range_given:
            members_qs = members_qs.filter(joined_at__gte=start_date, joined_at__lte=end_date)
        recent_members = MemberListSerializer(members_qs[:6], many=True).data
        pending_apps = BusinessApplicationSerializer(
            BusinessApplication.objects.filter(
                status__in=[ApplicationStatus.NEW, ApplicationStatus.REVIEWING, ApplicationStatus.CONTACTED]
            )[:6],
            many=True,
        ).data

        return Response(
            {
                "kpis": {
                    "active_users": f"{active_users:,}",
                    "active_businesses": f"{active_businesses:,}",
                    "monthly_revenue": fmt_compact(monthly_revenue),
                    "subscription_rate": subscription_rate.replace(".", ","),
                    "downloads": f"{downloads:,}",
                },
                "weekly": weekly,
                "monthly": monthly,
                "recent_members": recent_members,
                "pending_applications": pending_apps,
                "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            }
        )


# ---------------------------------------------------------------------------
# Analytics (Analitika)
# ---------------------------------------------------------------------------


class AnalyticsView(APIView):
    def get(self, request):
        today = timezone.now().date()
        p = self.request.query_params

        start = parse_date(p.get("start"))
        end = parse_date(p.get("end")) or today
        period = p.get("period")  # hafta / oy / jami
        if not start:
            if period == "hafta":
                start = end - timedelta(days=6)
            elif period == "oy":
                start = end - timedelta(days=29)
            else:
                start = end - timedelta(days=365)
        category = p.get("category")
        region = p.get("region")

        # --- Top stats -----------------------------------------------------
        last_activity = DailyActivity.objects.order_by("-date").first()
        today_active = last_activity.daily_active if last_activity else 0
        total_members = Member.objects.count()

        churned = Member.objects.exclude(churn_reason="")
        churn_rate = round(churned.count() / total_members * 100, 1) if total_members else 0

        expiring = Member.objects.filter(
            membership_end__gte=today, membership_end__lte=today + timedelta(days=7), is_blocked=False
        ).count()

        # --- Daily & monthly activity chart --------------------------------
        activity = []
        for i in range(5, -1, -1):
            m_start = add_months(today.replace(day=1), -i)
            m_end = add_months(m_start, 1)
            month_acts = DailyActivity.objects.filter(date__gte=m_start, date__lt=m_end)
            monthly_avg = month_acts.aggregate(t=Sum("daily_active"))["t"] or 0
            last = month_acts.order_by("-date").first()
            activity.append(
                {
                    "label": MONTH_LABELS_UZ[m_start.month - 1][:5],
                    "monthly": monthly_avg // max(month_acts.count(), 1) * 6,
                    "daily": last.daily_active if last else 0,
                }
            )

        # --- Funnel ---------------------------------------------------------
        stat = PlatformStat.objects.first()
        downloads = stat.downloads if stat else 0
        payment_opens = stat.payment_page_opens if stat else 0
        subscribed = Member.objects.filter(status=Status.PREMIUM).count()
        registered = max(stat.registrations if stat else 0, total_members)

        def pct(v):
            return f"{round(v / downloads * 100, 1) if downloads else 0}".rstrip("0").rstrip(".") + "%"

        funnel = [
            {"label": "Ilovani yuklab oldi", "value": downloads, "pct": "100%"},
            {"label": "Ro'yxatdan o'tdi", "value": registered, "pct": pct(registered)},
            {"label": "To'lov sahifasini ochdi", "value": payment_opens, "pct": pct(payment_opens)},
            {"label": "Obuna sotib oldi", "value": subscribed, "pct": pct(subscribed)},
        ]

        # --- Most visited categories (QR scans, last 30 days) ---------------
        tx = BusinessTransaction.objects.filter(
            status=TransactionStatus.SUCCESS, created_at__date__gte=start, created_at__date__lte=end
        )
        if category:
            tx = tx.filter(business__category=category)
        if region:
            tx = tx.filter(business__region=region)

        cat_rows = (
            tx.values("business__category")
            .annotate(visits=Count("id"), saved=Sum("original_amount") - Sum("final_amount"))
            .order_by("-visits")
        )
        businesses_per_cat = {
            row["category"]: row["n"]
            for row in Business.objects.filter(status=BusinessStatus.APPROVED)
            .values("category")
            .annotate(n=Count("id"))
        }
        categories = [
            {
                "category": row["business__category"],
                "visits": row["visits"],
                "businesses": businesses_per_cat.get(row["business__category"], 0),
                "saved": int(row["saved"] or 0),
            }
            for row in cat_rows
        ]

        # --- Churn breakdown -------------------------------------------------
        churn_total = churned.count() or 1
        churn_reasons = []
        for reason in ChurnReason.values:
            n = churned.filter(churn_reason=reason).count()
            churn_reasons.append(
                {"reason": reason, "count": n, "pct": round(n / churn_total * 100)}
            )
        churn_reasons.sort(key=lambda r: -r["count"])

        # --- Savings ---------------------------------------------------------
        # Total = every member's accumulated savings since the platform launched
        all_tx = BusinessTransaction.objects.filter(status=TransactionStatus.SUCCESS)
        total_saved = int(Member.objects.aggregate(t=Sum("savings_total"))["t"] or 0)
        month_tx = all_tx.filter(created_at__date__gte=today.replace(day=1))
        month_saved = int(
            (month_tx.aggregate(o=Sum("original_amount"))["o"] or 0)
            - (month_tx.aggregate(f=Sum("final_amount"))["f"] or 0)
        )
        top_saver = Member.objects.order_by("-savings_total").first()
        tx_saved = int(
            (all_tx.aggregate(t=Sum("original_amount"))["t"] or 0)
            - (all_tx.aggregate(t=Sum("final_amount"))["t"] or 0)
        )
        avg_per_visit = int(tx_saved / all_tx.count()) if all_tx.count() else 0
        weighted_discount = (
            Business.objects.filter(status=BusinessStatus.APPROVED).aggregate(
                a=Sum("discount_percent")
            )["a"]
            or 0
        )
        approved_count = Business.objects.filter(status=BusinessStatus.APPROVED).count() or 1
        avg_discount = round(weighted_discount / approved_count, 1)

        # Minimum / Maksimum tejalgan — a'zolar orasidagi eng kam va eng ko'p
        # jamg'arilgan tejash summasi (dizayndagi "Minimum/Maximum tejalgan").
        saved_members = Member.objects.filter(savings_total__gt=0)
        min_saved = int(saved_members.aggregate(m=Min("savings_total"))["m"] or 0)
        max_saved = int(Member.objects.aggregate(m=Max("savings_total"))["m"] or 0)

        savings_by_cat = (
            all_tx.values("business__category")
            .annotate(saved=Sum("original_amount") - Sum("final_amount"), month=Sum("final_amount"))
            .order_by("-saved")[:6]
        )
        savings_categories = [
            {
                "category": row["business__category"],
                "saved": int(row["saved"] or 0),
            }
            for row in savings_by_cat
        ]

        # --- Insights ---------------------------------------------------------
        acts = DailyActivity.objects.order_by("-date")[:30]
        peak_hours = [a.peak_hour for a in acts]
        peak_hour = max(set(peak_hours), key=peak_hours.count) if peak_hours else 18

        top_cat = categories[0]["category"] if categories else "—"
        top_cat_visits = categories[0]["visits"] if categories else 0

        top_city_row = (
            Member.objects.values("city").annotate(n=Count("id")).order_by("-n").first()
        )

        return Response(
            {
                "top": {
                    "today_active": f"{today_active:,}",
                    "total_members": f"{total_members:,}",
                    "churn_rate": f"{churn_rate}%".replace(".", ","),
                    "expiring_week": f"{expiring} a'zo",
                },
                "activity": activity,
                "funnel": funnel,
                "categories": categories,
                "churn": {"rate": f"{churn_rate}%".replace(".", ","), "reasons": churn_reasons},
                "savings": {
                    "total": total_saved,
                    "this_month": month_saved,
                    "top_member": {
                        "name": top_saver.name if top_saver else "—",
                        "amount": int(top_saver.savings_total) if top_saver else 0,
                    },
                    "avg_per_visit": avg_per_visit,
                    "avg_discount": f"{avg_discount}%",
                    "min_saved": min_saved,
                    "max_saved": max_saved,
                    "by_category": savings_categories,
                },
                "insights": {
                    "peak_hour": f"{peak_hour}:00",
                    "top_category": top_cat,
                    "top_category_visits": f"{top_cat_visits:,}",
                    "top_city": top_city_row["city"] if top_city_row else "—",
                    "top_city_members": f"{top_city_row['n']:,}" if top_city_row else "0",
                    "expiring_week": f"{expiring} a'zo",
                },
                "regions": [r for r in Member.objects.values_list("city", flat=True).distinct()],
            }
        )


class AnalyticsExportView(APIView):
    """JSON payload the frontend turns into a branded PDF report."""

    def get(self, request):
        tx = BusinessTransaction.objects.filter(status=TransactionStatus.SUCCESS)
        businesses_per_cat = {
            row["category"]: row["n"]
            for row in Business.objects.filter(status=BusinessStatus.APPROVED)
            .values("category")
            .annotate(n=Count("id"))
        }
        rows = [
            [
                row["business__category"],
                f"{row['visits']:,}",
                businesses_per_cat.get(row["business__category"], 0),
                f"{int(row['saved'] or 0):,} so'm",
            ]
            for row in tx.values("business__category")
            .annotate(visits=Count("id"), saved=Sum("original_amount") - Sum("final_amount"))
            .order_by("-visits")
        ]
        return Response(
            {
                "title": "Analitika — kategoriyalar kesimida",
                "columns": ["Kategoriya", "Tashriflar", "Hamkor bizneslar", "Tejangan summa"],
                "rows": rows,
            }
        )
