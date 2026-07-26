web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py run_seed && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
