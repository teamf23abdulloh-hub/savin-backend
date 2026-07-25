"""Savin Platform — barcha panellarning yagona URL xaritasi.

Avval ikkita portda ishlagan API endi bitta portda (8000) yashaydi:

    /api/v1/...          landing, biznes paneli, kassir paneli   (avval :8000)
    /api/v1/mobile/...   Android/iOS ilova                       (avval :8000)
    /api/auth/...        admin paneli — login/profil             (avval :8001)
    /api/...             admin paneli — dashboard, biznes, to'lov (avval :8001)
    /django-admin/       Django'ning o'z admin interfeysi

Tartib muhim: `api/v1/` va `api/auth/` `api/` dan oldin turishi kerak, aks holda
umumiy `api/` prefiksi ularni ham o'ziga tortib ketardi.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    """Render health-check va deploy tekshiruvi uchun engil endpoint."""
    return JsonResponse({"status": "ok", "service": "savin-platform"})


urlpatterns = [
    path('', health, name='root-health'),
    path('api/v1/health/', health, name='health'),

    path('django-admin/', admin.site.urls),

    # ---- Asosiy platforma: landing + biznes/kassir panellari ----
    path('api/v1/', include('users.urls')),
    path('api/v1/', include('businesses.urls')),
    path('api/v1/', include('discounts.urls')),
    path('api/v1/', include('payments.urls')),
    path('api/v1/', include('notifications.urls')),
    path('api/v1/', include('analytics.urls')),
    path('api/v1/', include('transactions.urls')),

    # ---- Mobil ilova (telefon orqali kiradigan mijozlar) ----
    path('api/v1/mobile/', include('mobileapi.urls')),

    # ---- Admin paneli ----
    path('api/auth/', include('accounts.urls')),
    path('api/', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
