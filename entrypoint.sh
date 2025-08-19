#!/bin/bash
set -e

# Выполняем миграции (не падаем, если БД пустая)
python manage.py migrate || true

# Создаём суперпользователя, если не существует
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
  python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); import os; u=os.environ.get('DJANGO_SUPERUSER_USERNAME'); e=os.environ.get('DJANGO_SUPERUSER_EMAIL'); p=os.environ.get('DJANGO_SUPERUSER_PASSWORD','password');
u and not U.objects.filter(username=u).exists() and U.objects.create_superuser(u,e,p)"
fi

export WORKERS=${SERVER_WORKERS:-3}
export TIMEOUT=${WORKER_TIMEOUT:-180}

exec gunicorn chatgpt_ui_server.wsgi:application --workers=$WORKERS --timeout $TIMEOUT --bind 0.0.0.0:8010 --access-logfile -