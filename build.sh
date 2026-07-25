#!/usr/bin/env bash
# Render build skripti (Build Command: ./build.sh)
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate
