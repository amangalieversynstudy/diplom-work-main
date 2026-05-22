"""Production Django settings for deployment."""

from .base import *

DEBUG = False
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# Cloudflare Tunnel / nginx ставят запрос как https, но к Daphne приходит http.
# Это говорит Django доверять заголовку X-Forwarded-Proto от прокси.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Список доменов, с которых разрешён POST/PUT/DELETE (нужно для cloudflared/ngrok/nginx).
# Пример .env: CSRF_TRUSTED_ORIGINS="https://*.trycloudflare.com,https://*.duckdns.org,https://my-domain.ru"
CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "https://*.trycloudflare.com,https://*.duckdns.org,https://*.loca.lt",
).split(",")
