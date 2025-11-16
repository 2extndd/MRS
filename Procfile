web: gunicorn --bind 0.0.0.0:$PORT --timeout 30 --log-level info wsgi:application
worker: python mercari_notifications.py worker
