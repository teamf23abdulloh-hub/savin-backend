"""Savin Platform — yagona backend sozlamalari.

Avval ikkita alohida Django loyihasi bor edi:
  * savin_django  (8000) — landing, biznes/kassir panellari va mobil ilova API'si
  * savin-backend (8001) — admin paneli

Endi ikkalasi bitta loyihaga birlashtirildi: bitta baza, bitta port, bitta
`python manage.py runserver`. Ular orasidagi HTTP "ko'prik" (webhook) chaqiruvlari
jarayon ichidagi to'g'ridan-to'g'ri funksiya chaqiruvlariga aylantirildi.

Ikkita User modeli muammosi qanday hal qilingan
-----------------------------------------------
Django'da AUTH_USER_MODEL faqat bitta bo'ladi. Shuning uchun:
  * `users.User`         — AUTH_USER_MODEL (mijoz, biznes egasi, kassir, admin),
                           JWT bilan autentifikatsiya qilinadi;
  * `accounts.AdminUser` — admin panel operatori; oddiy model bo'lib qoldi va
                           o'zining `accounts.AdminToken` tokeni hamda
                           `accounts.auth.AdminUserBackend` backendi bilan
                           ishlaydi (`Authorization: Token <key>`).
Shu tufayli admin panel kodi deyarli o'zgarishsiz qoldi.
"""

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# DEBUG endi standart holatda O'CHIQ. Lokal ishlashda `DJANGO_DEBUG=True`
# qo'yiladi. Avval standart True edi — agar hostingda bu o'zgaruvchi qo'yilmay
# qolsa, production'da to'liq xato izlari (traceback) va CORS hammaga ochiq
# bo'lib qolardi.
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"

_INSECURE_KEY = "django-insecure-CHANGE-ME-IN-PRODUCTION-kjv*b7nbpu5%!hi66"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _INSECURE_KEY)

# Production'da tasodifiy kalit majburiy — aks holda imzolangan cookie va
# parol tiklash tokenlarini soxtalashtirsa bo'ladi.
if not DEBUG and SECRET_KEY == _INSECURE_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY muhit o'zgaruvchisi qo'yilmagan. Production'da "
        "tasodifiy maxfiy kalit majburiy (Render: Environment -> Generate)."
    )

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # 3rd party
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',
    'corsheaders',

    # Asosiy platforma (landing + biznes/kassir panellari + mobil ilova)
    'users',
    'businesses',
    'discounts',
    'payments',
    'notifications',
    'analytics',
    'transactions',
    'mobileapi',

    # Admin paneli
    'accounts',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Whitenoise — Render'da statik fayllarni (admin CSS va h.k.) gunicorn
    # orqali to'g'ridan-to'g'ri xizmat qilish uchun
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Lokal dev: SQLite. Render/production: DATABASE_URL env o'rnatilsa o'sha
# ishlatiladi (Render'da SQLite ishlatib bo'lmaydi — har deploy'da disk tozalanadi).
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = 'users.User'

# `users.User` — USERNAME_FIELD sifatida email ishlatadi (ModelBackend),
# `accounts.AdminUser` esa login (username) bilan kiradi — o'z backendi orqali.
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'accounts.auth.AdminUserBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Whitenoise: siqilgan va keshlanadigan statik fayllar (production uchun)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- REST Framework ---
# Ikkala tizim ham bitta DRF konfiguratsiyasida yashaydi:
#   * JWT (Bearer)  — mijoz / biznes egasi / kassir (users.User)
#   * Token         — admin panel operatori (accounts.AdminUser)
# Ikkalasi turli `Authorization` kalit so'zini ishlatgani uchun to'qnashmaydi.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'accounts.authentication.AdminTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=6),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=14),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o
]
# Lokal devda (DEBUG=True) barcha frontendlarga ruxsat; production'da faqat
# CORS_ALLOWED_ORIGINS env'da ko'rsatilganlarga.
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOW_CREDENTIALS = True

# HTTPS orqasidagi admin/login formalar uchun (Render domeni misol:
# CSRF_TRUSTED_ORIGINS=https://savin-backend.onrender.com)
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

# Render (va boshqa PaaS'lar) so'rovni proxy orqali uzatadi — HTTPS ekanini
# shu header orqali bildiradi.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Production'da (DEBUG=False) HTTPS majburiy va cookie'lar faqat shifrlangan
# ulanish orqali yuboriladi. Lokal devda o'chiq — aks holda http://localhost
# ochilmay qolardi.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 yil
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"


# --- Ichki ko'prik (bridge) ---
# Ilgari ikkala backend bir-biriga HTTP webhook yuborardi. Endi ikkalasi bitta
# jarayonda bo'lgani uchun ko'prik to'g'ridan-to'g'ri funksiya chaqiradi —
# tarmoq so'rovi ham, timeout ham, "admin backend o'chiq" holati ham yo'q.
#
# Quyidagi token faqat eski public HTTP endpointlar uchun qoldirilgan (agar
# tashqi tizim hali ham o'sha manzillarga POST qilsa).
ADMIN_PANEL_BRIDGE_TOKEN = os.environ.get(
    "ADMIN_PANEL_BRIDGE_TOKEN", "savin-bridge-local" if DEBUG else ""
)
