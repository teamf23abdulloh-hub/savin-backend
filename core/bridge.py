"""Admin panel -> platforma yo'nalishi (ichki ko'prik).

Admin panelda ariza / chegirma so'rovi / referal so'rovi tasdiqlanganda yoki rad
etilganda natija platformaning o'z modellariga yoziladi: biznes egasi hisobi
yaratiladi, chegirma foizi yangilanadi, mijoz a'zoligi uzaytiriladi va h.k.

Ilgari bu alohida backendga HTTP POST edi (`urllib` + timeout + "backend
o'chiq" holati). Endi ikkala tizim bitta jarayonda va bitta bazada bo'lgani
uchun tegishli servis funksiyalari to'g'ridan-to'g'ri chaqiriladi.

Import'lar ataylab funksiya ichida: `core` ilovasi yuklanayotganda
`businesses` / `discounts` / `mobileapi` hali tayyor bo'lmasligi mumkin.
"""

import logging

logger = logging.getLogger(__name__)


def notify_main_backend(application, action, reason=""):
    """Ariza natijasini platforma tomoniga qo'llaydi.

    `application` — admin paneldagi `core.BusinessApplication`. Uning
    `source_id` maydoni platformadagi `businesses.Application` ID'si; bo'sh
    bo'lsa (ariza ko'prik orqali kelmagan) hech narsa qilinmaydi.
    """
    from businesses.models import Application
    from businesses.services import (
        ApplicationApproveError,
        approve_application,
        reject_application,
    )

    if not application.source_id:
        return False

    try:
        target = Application.objects.get(pk=application.source_id)
    except (Application.DoesNotExist, ValueError, TypeError):
        logger.warning(
            "Ariza platformada topilmadi (source_id=%s)", application.source_id
        )
        return False

    try:
        if action == "approve":
            approve_application(target)
        elif action == "reject":
            reject_application(target, reason=reason)
        else:
            return False
    except ApplicationApproveError as exc:
        logger.warning("Arizani tasdiqlab bo'lmadi: %s", exc)
        return False
    return True


def review_referral_on_main(source_id, action, reason=""):
    """Referal mukofot so'rovi natijasini platforma tomoniga qo'llaydi:
    tasdiqlansa mijoz a'zoligi uzaytiriladi, rad etilsa mijozga sabab bilan
    bildirishnoma boradi."""
    from mobileapi.services import ReferralReviewError, review_referral_request

    if not source_id:
        return False
    try:
        review_referral_request(source_id, action, reason)
    except ReferralReviewError as exc:
        logger.warning("Referal so'rovi qo'llanmadi: %s", exc)
        return False
    return True


def review_discount_on_main(source_id, action, reason=""):
    """Chegirma so'rovi natijasini platforma tomoniga qo'llaydi.

    So'rov holati yangilanadi va biznes egasiga (biznes panelning
    Bildirishnomalar bo'limiga) avtomatik bildirishnoma boradi.
    """
    from discounts.models import DiscountChangeRequest
    from discounts.views import apply_discount_review

    if not source_id or action not in ("approve", "reject"):
        return False

    try:
        change_request = DiscountChangeRequest.objects.get(pk=source_id)
    except (DiscountChangeRequest.DoesNotExist, ValueError, TypeError):
        logger.warning("Chegirma so'rovi topilmadi (id=%s)", source_id)
        return False

    if change_request.status != DiscountChangeRequest.Status.PENDING:
        logger.warning("Chegirma so'rovi allaqachon ko'rib chiqilgan (id=%s)", source_id)
        return False

    apply_discount_review(change_request, action, reject_reason=reason)
    return True
