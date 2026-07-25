"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()


# --- Ishga tushishda avtomatik migratsiya (production) ---
# Ba'zi hostinglarda (masalan Railway'da dashboard'dagi "Custom Start Command"
# start buyrug'ini almashtirsa) `manage.py migrate` deploy vaqtida umuman
# ishlamay qolishi mumkin — natijada bazada jadvallar yaratilmay, API 500
# qaytaradi. Shu holatga qarshi kafolat sifatida, start buyrug'iga bog'liq
# bo'lmagan holda, ishga tushishda migratsiyani bir marta bajaramiz.
#
# Standart holatda YOQIQ (AUTO_MIGRATE). O'chirish uchun: AUTO_MIGRATE=False.
# Gunicorn bitta worker bilan ishga tushgani uchun poyga (race) xavfi yo'q.
if os.environ.get("AUTO_MIGRATE", "True") == "True":
    try:
        from django.core.management import call_command
        call_command("migrate", "--noinput")
    except Exception as exc:  # migratsiya xatosi ilovani butunlay to'xtatmasin
        import logging
        logging.getLogger(__name__).error("Auto-migrate xatosi: %s", exc)
