from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.models import Application, Business, Cashier, Category, Service
from businesses.serializers import (
    ApplicationLocationSetSerializer,
    ApplicationReviewSerializer,
    ApplicationSerializer,
    ApplicationStep1Serializer,
    ApplicationStep2Serializer,
    ApplicationStep3Serializer,
    ApplicationStep4Serializer,
    BusinessDashboardSerializer,
    BusinessSerializer,
    CashierCreateSerializer,
    cashier_email_from_login,
    CashierSerializer,
    CategorySerializer,
    PartnershipStatusUpdateSerializer,
    ServiceSerializer,
)
from businesses.services import (
    ApplicationApproveError,
    approve_application,
    reject_application,
)
from discounts.models import DiscountUsage
from notifications.models import UserNotification
from users.models import User
from users.permissions import IsAdminRole, IsBusinessOwner, IsCashier


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


# ==================== ARIZA QOLDIRISH (Wizard) ====================


class MyApplicationsView(generics.ListAPIView):
    """Foydalanuvchining o'z arizalari ro'yxati."""

    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Application.objects.filter(applicant=self.request.user)


class ApplicationDetailView(generics.RetrieveAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    queryset = Application.objects.all()

    def get_queryset(self):
        user = self.request.user
        if user.role in (User.Role.ADMIN, User.Role.SUPERADMIN):
            return Application.objects.all()
        return Application.objects.filter(applicant=user)


class ApplicationWizardStep1View(generics.CreateAPIView):
    """1/4 qadam — Biznes. Yangi ariza yaratadi (draft)."""

    serializer_class = ApplicationStep1Serializer
    permission_classes = [AllowAny]


class ApplicationWizardStepUpdateView(APIView):
    """2/4, 3/4, 4/4 qadamlarni to'ldirish uchun umumiy view."""

    permission_classes = [AllowAny]

    authentication_classes = []

    step_serializers = {
        2: ApplicationStep2Serializer,
        3: ApplicationStep3Serializer,
        4: ApplicationStep4Serializer,
    }

    def patch(self, request, pk, step):
        step = int(step)
        serializer_class = self.step_serializers.get(step)
        if not serializer_class:
            return Response({"detail": "Noto'g'ri qadam."}, status=400)

        application = get_object_or_404(
            Application, pk=pk
        )  # applicant=request.user olib tashlandi
        serializer = serializer_class(application, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(ApplicationSerializer(application).data)


class PanelLoginCheckView(APIView):
    """Landing 4-qadam: biznes panel logini bandligini jonli tekshirish.

    GET /applications/check-login/?login=example@savin.uz
    -> {"available": true/false}
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        login = (request.query_params.get("login") or "").strip().lower()
        if not login:
            return Response(
                {"detail": "login parametri majburiy."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        taken = (
            User.objects.filter(email__iexact=login).exists()
            or Application.objects.filter(panel_login__iexact=login)
            .exclude(status=Application.Status.REJECTED)
            .exists()
        )
        return Response({"available": not taken})


class AdminBridgeApplicationReviewView(APIView):
    """Alohida admin panel backendi arizani tasdiqlab/rad etib bo'lgach,
    natijani shu yerga qaytaradi — asosiy bazada ham User/Business yaratiladi
    (biznes egasi landing'da tanlagan login/parol bilan panelга kira olishi
    uchun). Oddiy token bilan himoyalangan (ADMIN_PANEL_BRIDGE_TOKEN).
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

        application = get_object_or_404(
            Application, pk=request.data.get("source_id")
        )
        action = request.data.get("action")
        if action == "approve":
            try:
                business = approve_application(application)
            except ApplicationApproveError as exc:
                return Response(
                    {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {"status": "approved", "business_id": business.id}
            )
        if action == "reject":
            reject_application(
                application, reason=request.data.get("reason", "")
            )
            return Response({"status": "rejected"})
        return Response(
            {"detail": "action approve yoki reject bo'lishi kerak."},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ==================== ADMIN PANEL: Biznes boshqaruvi ====================


class AdminApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    """Arizalar ro'yxati -> Yangi ariza ko'rish."""

    queryset = Application.objects.select_related("category", "applicant").all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "category", "business_type"]
    search_fields = ["business_name", "applicant__email", "phone_number"]
    ordering_fields = ["created_at"]


class AdminApplicationReviewView(APIView):
    """
    Tasdiqlash (listing faollashadi) / Rad etish (sabab yoziladi)
    """

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        serializer = ApplicationReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]

        # Tasdiqlash/rad etish logikasi services.py da — bridge endpoint
        # (admin panel backendidan keladigan) bilan bir xil ishlashi uchun.
        if action == "approve":
            try:
                business = approve_application(application, reviewer=request.user)
            except ApplicationApproveError as exc:
                return Response(
                    {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
                )
            return Response(BusinessSerializer(business).data)

        reject_application(
            application,
            reason=serializer.validated_data.get("rejection_reason", ""),
            reviewer=request.user,
        )
        return Response(ApplicationSerializer(application).data)


class AdminApplicationSetLocationView(APIView):
    """
    Operator ariza beruvchi bilan birga aniq lokatsiyani (lat/long) belgilaydi
    (Wizard Step 3 dagi: "Aniq lokatsiyani operator siz bilan birga belgilaydi").
    """

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        serializer = ApplicationLocationSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application.latitude = serializer.validated_data["latitude"]
        application.longitude = serializer.validated_data["longitude"]
        application.save(update_fields=["latitude", "longitude"])
        return Response(ApplicationSerializer(application).data)


class AdminBusinessViewSet(viewsets.ReadOnlyModelViewSet):
    """Faol Bizneslar ro'yxati -> Biznes profili ko'rish."""

    queryset = Business.objects.select_related("category", "owner").all()
    serializer_class = BusinessSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["partnership_status", "category", "is_active"]
    search_fields = ["name", "owner__email", "phone_number"]


class AdminBusinessStopPartnershipView(APIView):
    """Hamkorlikni to'xtatish."""

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        business = get_object_or_404(Business, pk=pk)
        serializer = PartnershipStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        business.partnership_status = serializer.validated_data["partnership_status"]
        if business.partnership_status == Business.PartnershipStatus.STOPPED:
            business.is_active = False
        business.save()
        return Response(BusinessSerializer(business).data)


class AdminBusinessStatsView(APIView):
    """Statistikasini ko'rish (Admin tomonidan)."""

    permission_classes = [IsAdminRole]

    def get(self, request, pk):
        business = get_object_or_404(Business, pk=pk)
        usages = DiscountUsage.objects.filter(business=business)
        data = {
            "total_customers": usages.values("customer").distinct().count(),
            "total_discount_amount": usages.aggregate(s=Sum("discount_amount"))["s"]
            or 0,
            "total_transactions": usages.count(),
        }
        return Response(data)


# ==================== BIZNES EGASI: Dashboard, Profil, Kassirlar ====================


class MyBusinessView(generics.RetrieveUpdateAPIView):
    """Biznes egasi o'z biznes profilini ko'rish/tahrirlash (Profil / Sozlama)."""

    serializer_class = BusinessSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwner]

    def get_object(self):
        return get_object_or_404(Business, owner=self.request.user)


class MyBusinessDashboardView(APIView):
    """Dashboard (Bosh sahifa): Bugungi stat, daromad, mijozlar."""

    permission_classes = [IsAuthenticated, IsBusinessOwner]

    def get(self, request):
        business = get_object_or_404(Business, owner=request.user)
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
            "today_customers": today_usages.values("customer").distinct().count(),
            "today_discount_amount": discount_total,
            # Daromad — mijozlar amalda to'lagan summa (xarid - chegirma).
            # Statistika sahifasidagi hisob-kitob bilan bir xil bo'lishi uchun.
            "today_revenue": purchase_total - discount_total,
            "total_customers": DiscountUsage.objects.filter(business=business)
            .values("customer")
            .distinct()
            .count(),
            "active_discount_percent": (
                business.application.discount_percent if business.application else 0
            ),
        }
        serializer = BusinessDashboardSerializer(data)
        return Response(serializer.data)


class MyServiceListCreateView(generics.ListCreateAPIView):
    """Xizmatlar katalogi: ro'yxat / yangi xizmat qo'shish (biznes egasi)."""

    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwner]
    pagination_class = None

    def get_queryset(self):
        business = get_object_or_404(Business, owner=self.request.user)
        return Service.objects.filter(business=business)

    def perform_create(self, serializer):
        business = get_object_or_404(Business, owner=self.request.user)
        serializer.save(business=business)


class MyServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Xizmatni tahrirlash / o'chirish (biznes egasi)."""

    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwner]

    def get_queryset(self):
        business = get_object_or_404(Business, owner=self.request.user)
        return Service.objects.filter(business=business)


class CashierServiceListView(generics.ListAPIView):
    """Kassir uchun: o'z biznesining faol xizmatlar ro'yxati (tranzaksiyada tanlash)."""

    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated, IsCashier]
    pagination_class = None

    def get_queryset(self):
        cashier = get_object_or_404(Cashier, user=self.request.user, is_active=True)
        return Service.objects.filter(business=cashier.business, is_active=True)


class MyCashierListCreateView(generics.ListCreateAPIView):
    """Kassirlar: Ro'yxat ko'rish / Kassir qo'shish (Email, parol berish)."""

    serializer_class = CashierSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwner]
    # Frontend to'liq ro'yxat kutadi (o'zi sahifalamaydi)
    pagination_class = None

    def get_queryset(self):
        business = get_object_or_404(Business, owner=self.request.user)
        return Cashier.objects.filter(business=business).select_related("user")

    def create(self, request, *args, **kwargs):
        business = get_object_or_404(Business, owner=request.user)
        serializer = CashierCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Kassir login orqali kiradi, auth esa email bilan ishlaydi —
        # shuning uchun login'dan ichki email hosil qilamiz.
        login = data["login"].strip()
        email = cashier_email_from_login(login)

        cashier_user = User.objects.create_user(
            username=email,
            email=email,
            password=data["password"],
            role=User.Role.CASHIER,
            phone_number=data.get("phone", "") or None,
        )
        cashier = Cashier.objects.create(
            business=business,
            user=cashier_user,
            full_name=data["full_name"],
            phone=data.get("phone", ""),
            login=login,
            password_plain=data["password"],
            is_active=data.get("is_active", True),
        )
        return Response(CashierSerializer(cashier).data, status=status.HTTP_201_CREATED)


class MyCashierDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CashierSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwner]

    def get_queryset(self):
        business = get_object_or_404(Business, owner=self.request.user)
        return Cashier.objects.filter(business=business).select_related("user")

    def perform_update(self, serializer):
        cashier = serializer.save()
        # Kassir faolsizlantirilsa login ham bloklanadi (qayta yoqilsa — ochiladi),
        # aks holda o'chirilgan kassir tizimga kiraverar edi.
        if cashier.user.is_active != cashier.is_active:
            cashier.user.is_active = cashier.is_active
            cashier.user.save(update_fields=["is_active"])

    def perform_destroy(self, instance):
        user = instance.user
        instance.delete()
        # Kassir o'chirilganda unga berilgan login hisobi ham yopiladi —
        # aks holda "yetim" hisob tizimga kiraverar edi.
        user.is_active = False
        user.save(update_fields=["is_active"])
