# DIQQAT: bu yerda HECH QACHON seed/flush buyrug'i bo'lmasin!
# Ilgari `python manage.py run_seed` turardi — u SEED env qiymatiga qarab
# bazani tozalab qayta to'ldirardi, ya'ni HAR DEPLOYDA yangi qo'shilgan
# ma'lumotlar o'chib ketardi. Demo ma'lumot faqat Railway Console'dan
# QO'LDA yuritiladi (README_DEPLOY.md ga qarang).
web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && (python manage.py sync_members --apply --quiet || echo 'sync_members xato berdi') && (python manage.py seed_services --apply --quiet || echo 'seed_services xato berdi') && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
