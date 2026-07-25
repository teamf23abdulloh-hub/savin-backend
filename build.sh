#!/usr/bin/env bash
# Build skripti (Build Command: ./build.sh)
set -o errexit

pip install -r requirements.txt

# DIQQAT: `migrate` bu yerda EMAS. Railway'da Postgres ichki host
# (savin-db.railway.internal) faqat RUNTIME'da resolve bo'ladi — build
# paytida bazaga ulanib bo'lmaydi. Shuning uchun migratsiya startCommand'da
# (railway.json / Procfile) runtime'da ishlaydi. collectstatic bazaga
# ulanmaydi, shuning uchun bu yerda qolishi xavfsiz.
python manage.py collectstatic --noinput
