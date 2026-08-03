import hmac
import logging
import os
import re

from django.conf import settings
from django.db.models import Avg, Count, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from businesses.models import Business, Category
from transactions.models import Transaction
from mobileapi import sms
from mobileapi.models import CustomerNotification, PhoneOtp, ReferralRequest
from mobileapi.serializers import (
    MobileBusinessSerializer,
    MobileCategorySerializer,
    MobileNotificationSerializer,
    MobileUserSerializer,
)
from mobileapi.services import ReferralReviewError, review_referral_request
from users.models import Membership, User

# SMS tasdiqlash `mobileapi/sms.py` da: har safar tasodifiy kod yaratiladi,
# xeshlanib saqlanadi, 5 daqiqa amal qiladi va 5 tadan ortiq urinish
# qabul qilinmaydi. Kredensiallar (ESKIZ_EMAIL/ESKIZ_PASSWORD) qo'yilmaguncha
# test rejimida ishlaydi — kod javobda `dev_otp` sifatida qaytadi.

# Click/Payme hali ulanmagan. Yoqilganda a'zolik to'lovsiz beriladi (demo).
# Haqiqiy foydalanuvchilar uchun DEMO_PAYMENTS=False qilinishi SHART.
DEMO_PAYMENTS = os.environ.get("DEMO_PAYMENTS", "True") == "True"


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class MobileRegisterView(APIView):
    """Telefon orqali ro'yxatdan o'tish (mijoz) va tasdiqlash kodini yuborish.

    Foydalanuvchi bo'lmasa yaratiladi, bo'lsa ismi yangilanadi (qayta kirish).
    Test rejimida (provayder ulanmagan) kod javobda `dev_otp` bo'lib qaytadi.
    Shu endpoint kodni QAYTA yuborish uchun ham ishlatiladi — 60 soniyalik
    oraliqdan tez chaqirilsa 429 va `retry_after` qaytadi.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        first_name = (request.data.get("first_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()
        phone = (request.data.get("phone_number") or "").strip()

        if not phone:
            return Response({"phone_number": ["Telefon raqami majburiy."]}, status=400)

        digits = _digits(phone)
        username = phone
        email = f"{digits}@customer.savin.local"

        # Ism darhol `defaults`ga qo'yiladi — aks holda foydalanuvchi avval
        # ismsiz yaratilib, admin panelga ketadigan bildirishnomada ism
        # o'rniga telefon raqami chiqib qolardi.
        user, created = User.objects.get_or_create(
            phone_number=phone,
            role=User.Role.CUSTOMER,
            defaults={
                "username": username,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        # Ism kiritilgan bo'lsa yangilaymiz
        changed = False
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            changed = True
        if changed:
            user.save(update_fields=["first_name", "last_name"])

        # Kodni tez-tez qayta so'rashdan himoya
        wait = sms.seconds_until_resend(phone)
        if wait:
            return Response(
                {
                    "detail": f"Yangi kod so'rash uchun {wait} soniya kuting.",
                    "retry_after": wait,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        _otp, dev_code, sent = sms.create_and_send(phone)

        # SMS ketmagan bo'lsa buni YASHIRMAYMIZ. Avval javob har doim "ok"
        # edi va foydalanuvchi kod kiritish ekranida hech qachon kelmaydigan
        # SMSni kutib qolardi — sabab esa faqat server logida qolardi.
        #
        # Istisno: `SMS_ALLOW_OTP_IN_RESPONSE` yoqilgan bo'lsa kod javobda
        # keladi (`dev_code`) — bunda oqim uzilmaydi, foydalanuvchi kira oladi.
        if not sent and dev_code is None:
            # Kod yozuvi bazada qoladi, ya'ni qayta yuborish oralig'i kuchda —
            # provayder ishlamayotganda ketma-ket urinishlar uni yanada
            # bo'g'masin. Shuning uchun kutish vaqtini xabarda aytamiz.
            retry_after = sms.seconds_until_resend(phone)
            return Response(
                {
                    "detail": (
                        "Tasdiqlash kodini yuborib bo'lmadi. "
                        f"{retry_after} soniyadan keyin qayta urinib ko'ring yoki "
                        "qo'llab-quvvatlash xizmatiga murojaat qiling."
                    ),
                    "sms_failed": True,
                    "retry_after": retry_after,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = {
            "phone_number": phone,
            "is_new": created,
            "test_mode": sms.is_test_mode(),
            "expires_in": PhoneOtp.TTL_SECONDS,
            "resend_after": PhoneOtp.RESEND_COOLDOWN_SECONDS,
        }
        # Kod faqat test rejimida qaytadi — haqiqiy rejimda hech qachon
        if dev_code is not None:
            payload["dev_otp"] = dev_code
        return Response(payload, status=status.HTTP_200_OK)


class MobileLoginView(APIView):
    """Telefon + OTP bilan kirish. Javob: {access, refresh, user} (flat)."""

    permission_classes = [AllowAny]

    def post(self, request):
        phone = (request.data.get("phone_number") or "").strip()
        otp = (request.data.get("otp_code") or "").strip()

        if not phone:
            return Response({"detail": "Telefon raqami majburiy."}, status=400)

        # OTP MAJBURIY. Avval `if otp and otp != DEV_OTP` edi — bo'sh kod
        # yuborilsa tekshiruv butunlay o'tkazib yuborilar va istalgan telefon
        # raqamiga kodsiz kirish mumkin edi.
        if not otp:
            return Response({"detail": "Tasdiqlash kodi majburiy."}, status=400)

        # Kod bazadagi xesh bilan solishtiriladi (muddat va urinishlar bilan)
        ok, error = sms.verify(phone, otp)
        if not ok:
            return Response({"detail": error}, status=400)

        try:
            user = User.objects.get(phone_number=phone, role=User.Role.CUSTOMER)
        except User.DoesNotExist:
            return Response(
                {"detail": "Bu raqam ro'yxatdan o'tmagan. Avval ro'yxatdan o'ting."},
                status=404,
            )

        if user.is_blocked:
            return Response({"detail": "Foydalanuvchi bloklangan."}, status=403)

        user.last_seen_at = timezone.now()
        user.save(update_fields=["last_seen_at"])

        tokens = _tokens_for(user)
        return Response(
            {
                **tokens,
                "user": MobileUserSerializer(user, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


class MobileMeView(APIView):
    """Joriy mijoz profili (GET) va tahrirlash (PATCH)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MobileUserSerializer(request.user, context={"request": request}).data)

    def patch(self, request):
        user = request.user
        for field in ["first_name", "last_name", "email"]:
            if field in request.data:
                setattr(user, field, request.data.get(field) or "")
        if "avatar" in request.FILES:
            user.avatar = request.FILES["avatar"]
        user.save()
        return Response(MobileUserSerializer(user, context={"request": request}).data)

    def delete(self, request):
        # Xavfsizlik uchun jismonan o'chirmasdan deaktivatsiya
        user = request.user
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class MobileCategoryListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cats = Category.objects.filter(is_active=True).prefetch_related("businesses")
        return Response(MobileCategorySerializer(cats, many=True).data)


class MobileBusinessListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = Business.objects.filter(is_active=True).select_related("category", "application")
        category = request.query_params.get("category")
        search = request.query_params.get("search")
        if category:
            qs = qs.filter(category_id=category)
        if search:
            qs = qs.filter(name__icontains=search)
        return Response(MobileBusinessSerializer(qs, many=True).data)


class MobileMembershipActivateView(APIView):
    """Premium a'zolikni faollashtirish/uzaytirish — TEST/DEMO rejim.

    Haqiqiy to'lov (Click/Payme) hali ulanmagan; kalitlar qo'shilganda shu
    yerda to'lov tekshiruvi bo'ladi.

    DIQQAT: to'lov tekshiruvi yo'q bo'lgani uchun bu endpoint faqat
    DEMO_PAYMENTS yoqilganda ishlaydi — aks holda har qanday foydalanuvchi
    o'ziga bepul Premium berib olishi mumkin edi.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not DEMO_PAYMENTS:
            return Response(
                {"detail": "To'lov tizimi hali ulanmagan. Keyinroq urinib ko'ring."},
                status=503,
            )
        try:
            months = int(request.data.get("plan_months", 1))
        except (TypeError, ValueError):
            months = 1
        months = max(1, min(months, 12))

        user = request.user
        membership, _ = Membership.objects.get_or_create(user=user)
        now = timezone.now()
        base = membership.expires_at if membership.expires_at and membership.expires_at > now else now
        membership.expires_at = base + timezone.timedelta(days=30 * months)
        membership.status = Membership.Status.ACTIVE
        membership.save()

        CustomerNotification.objects.create(
            user=user,
            title="Premium faollashtirildi",
            body=f"{months} oylik Premium a'zolik faol. Chegirmalardan bemalol foydalaning!",
            kind=CustomerNotification.Kind.MEMBERSHIP,
        )

        return Response(
            {
                "detail": "Premium faollashtirildi (demo).",
                "user": MobileUserSerializer(user, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


class MobileNotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = CustomerNotification.objects.filter(user=request.user)[:50]
        return Response(MobileNotificationSerializer(qs, many=True).data)


def _tx_to_mobile(tx):
    """Transaction -> mobil ilova kutgan shakl."""
    return {
        "id": tx.id,
        "business_name": tx.business.name if tx.business_id else "",
        "category_name": tx.service_category or (tx.business.category.name if tx.business_id else ""),
        "district": tx.business.city_district if tx.business_id else "",
        "discount_percent": tx.discount_percent,
        "original_amount": int(tx.base_price or 0),
        "saved_amount": int(tx.discount_amount or 0),
        "created_at": tx.created_at.isoformat(),
    }


class MobileTransactionView(APIView):
    """Mijozning chegirma tarixi (GET) va yangi chegirma yozish (POST/redeem).

    Mijoz telefon raqami orqali bog'lanadi (Transaction.customer_phone).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        phone = request.user.phone_number or ""
        qs = (
            Transaction.objects.filter(customer_phone=phone, status="completed")
            .select_related("business", "business__category")
            .order_by("-created_at")
        )
        return Response([_tx_to_mobile(t) for t in qs])

    def post(self, request):
        user = request.user
        data = request.data
        business = None
        business_id = data.get("business")
        if business_id:
            business = Business.objects.filter(id=business_id).first()
        if business is None:
            # Demo/kassa integratsiyasisiz — istalgan faol biznesga bog'laymiz
            business = Business.objects.filter(is_active=True).first()
        if business is None:
            return Response({"detail": "Biznes topilmadi."}, status=400)

        try:
            base_price = int(data.get("original_amount", 0) or 0)
            discount_percent = int(data.get("discount_percent", 0) or 0)
        except (TypeError, ValueError):
            return Response({"detail": "Summa/foiz noto'g'ri."}, status=400)

        tx = Transaction.objects.create(
            business=business,
            customer_name=user.get_full_name() or user.username,
            customer_phone=user.phone_number or "",
            service_name="Chegirma",
            service_category=data.get("category_name", "") or "",
            base_price=base_price,
            discount_percent=discount_percent,
            status="completed",
        )
        return Response(_tx_to_mobile(tx), status=status.HTTP_201_CREATED)


class MobileTransactionStatsView(APIView):
    """Hamyon statistikasi — mijozning haqiqiy tranzaksiyalaridan hisoblanadi."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        phone = request.user.phone_number or ""
        qs = Transaction.objects.filter(customer_phone=phone, status="completed").select_related(
            "business", "business__category"
        )

        now = timezone.now()
        agg = qs.aggregate(
            visits=Count("id"),
            avg_pct=Avg("discount_percent"),
            saved_all=Sum("discount_amount"),
        )
        saved_month = qs.filter(created_at__year=now.year, created_at__month=now.month).aggregate(
            s=Sum("discount_amount")
        )["s"] or 0
        saved_year = qs.filter(created_at__year=now.year).aggregate(s=Sum("discount_amount"))["s"] or 0

        by_category = {}
        for t in qs:
            cat = t.service_category or (t.business.category.name if t.business_id else "Boshqa")
            by_category[cat] = by_category.get(cat, 0) + int(t.discount_amount or 0)

        return Response(
            {
                "visits": agg["visits"] or 0,
                "avg_discount_percent": round(float(agg["avg_pct"] or 0), 1),
                "saved_this_month": int(saved_month),
                "saved_this_year": int(saved_year),
                "saved_all_time": int(agg["saved_all"] or 0),
                "by_category": by_category,
            }
        )


class MobileReferralRequestView(APIView):
    """Mijoz 3 do'st taklif qilgach mukofot so'rovini yuboradi.

    So'rov saqlanadi (admin panelning 'So'rovlar' bo'limi uchun). Admin
    tasdiqlash/rad etish oqimi keyingi bosqichda admin backend + panel bilan
    to'liq ulanadi.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        invited = int(request.data.get("invited_count", 3) or 3)
        req = ReferralRequest.objects.create(
            customer=request.user,
            invited_count=invited,
        )
        # Admin panelga (savin-backend) uzatamiz — best-effort (xato bo'lsa
        # ham mijozga so'rov yuborildi deb ko'rsatamiz).
        _notify_admin_referral(request.user, req, invited)
        return Response(
            {"detail": "So'rov yuborildi.", "id": str(req.id), "status": req.status},
            status=status.HTTP_201_CREATED,
        )


def _notify_admin_referral(user, req, invited):
    """So'rovni admin panelning "Referal so'rovlari" bo'limiga chiqaradi.

    Avval bu alohida backendga HTTP POST edi; endi ikkala tizim bitta jarayonda
    bo'lgani uchun to'g'ridan-to'g'ri chaqiriladi. Best-effort: xato bo'lsa
    mijozning so'rov yuborish oqimi buzilmasin.
    """
    from core.inbox import receive_referral_request

    try:
        receive_referral_request(
            {
                "source_id": str(req.id),
                "member_name": user.get_full_name() or user.username,
                "member_phone": user.phone_number or "",
                "invited_count": invited,
            }
        )
    except Exception as exc:  # noqa: BLE001 — asosiy oqim buzilmasin
        logger.warning("Admin panelga referal so'rovi uzatilmadi: %s", exc)


class MobileReferralStatusView(APIView):
    """Mijozning oxirgi referal so'rovi holati — ilova buni tekshirib, tasdiqlansa
    referal hisoblagichini 0 ga qaytaradi (yangi tsikl)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        ref = ReferralRequest.objects.filter(customer=request.user).first()
        if ref is None:
            return Response({"status": None, "reason": ""})
        return Response({"status": ref.status, "reason": ref.reason})


class MobileReferralReviewBridgeView(APIView):
    """Admin panel (savin-backend) referal so'rovini tasdiqlab/rad etganda
    natijani shu yerga qaytaradi (bridge token bilan). Tasdiqlansa mijoz
    a'zoligi +1 oyga uzayadi va mijozga bildirishnoma boradi; rad etilsa —
    sabab bilan bildirishnoma boradi."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = request.data.get("token")
        expected = getattr(settings, "ADMIN_PANEL_BRIDGE_TOKEN", "")
        if not expected or token != expected:
            return Response({"detail": "Ruxsat yo'q."}, status=403)

        try:
            ref = review_referral_request(
                request.data.get("request_id"),
                request.data.get("action"),
                request.data.get("reason") or "",
            )
        except ReferralReviewError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response({"detail": "ok", "status": ref.status})


class SmsStatusView(APIView):
    """SMS sozlamalari holati — tashxis uchun.

    Ro'yxatdan o'tmasdan (va SMS yubormasdan) provayder ulanganini
    tekshirish imkonini beradi. Maxfiy qiymatlar QAYTMAYDI — faqat
    "qo'yilganmi" degan bayroqlar.

    Lokal ishlashda (DEBUG=True) ochiq. Production'da esa yopiq: javobda
    muhit o'zgaruvchilari nomlari va SMS matni bor, ular begonaga kerak
    emas. Ochish uchun `SMS_STATUS_TOKEN` qo'yiladi va so'rovga
    `?token=...` (yoki `X-Sms-Status-Token` sarlavhasi) qo'shiladi.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        if not settings.DEBUG:
            expected = os.environ.get("SMS_STATUS_TOKEN", "").strip()
            given = (
                request.headers.get("X-Sms-Status-Token")
                or request.query_params.get("token")
                or ""
            ).strip()
            if not expected or not hmac.compare_digest(given, expected):
                return Response({"detail": "Ruxsat yo'q."}, status=403)
        return Response(sms.diagnostics())
