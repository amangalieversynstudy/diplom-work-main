web: cd backend && python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 60 --access-logfile -
