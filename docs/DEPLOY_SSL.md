# Развёртывание RPG Academy в production с HTTPS

## Шаг 0. Подготовка сервера

```bash
# Заполни секреты — без них стек не стартует
cp .env.example .env.prod
nano .env.prod
# Минимум: SECRET_KEY, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD,
# ALLOWED_HOSTS=your-real-domain.com,www.your-real-domain.com,
# CSRF_TRUSTED_ORIGINS=https://your-real-domain.com,
# FRONTEND_URL=https://your-real-domain.com,
# NEXT_PUBLIC_API_BASE=https://your-real-domain.com/api,
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend + EMAIL_HOST/USER/PASSWORD,
# GEMINI_API_KEY=<ключ из aistudio.google.com>

# Замени плейсхолдер домена в nginx.conf
sed -i 's/rpg-academy.example.com/your-real-domain.com/g' nginx.conf

# Создай папки для certbot и бэкапов
mkdir -p ./certbot/www ./certbot/conf ./backups
```

## Шаг 1. Выпуск SSL — 3 bash-команды

```bash
# 1. Стартуем nginx с BOOTSTRAP-конфигом (HTTP-only, для ACME-challenge)
docker run --rm -d --name rpg-nginx-bootstrap \
  -p 80:80 \
  -v "$PWD/nginx.bootstrap.conf:/etc/nginx/nginx.conf:ro" \
  -v "$PWD/certbot/www:/var/www/certbot:ro" \
  nginx:1.27-alpine

# 2. Выпускаем сертификат webroot-методом
docker run --rm \
  -v "$PWD/certbot/conf:/etc/letsencrypt" \
  -v "$PWD/certbot/www:/var/www/certbot" \
  certbot/certbot:latest certonly --webroot -w /var/www/certbot \
  -d your-real-domain.com -d www.your-real-domain.com \
  --email admin@your-real-domain.com --agree-tos --no-eff-email --non-interactive

# 3. Сносим bootstrap-nginx и поднимаем полный prod-стек с HTTPS
docker stop rpg-nginx-bootstrap && \
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

После этих трёх команд:
- HTTP (80) автоматически редиректит на HTTPS (301);
- HTTPS (443) терминируется в nginx, проксируется в backend/frontend;
- сертификат продлевается контейнером `certbot` каждые 12 часов (idempotent, обновит только при сроке <30 дней);
- HSTS, X-Frame-Options, X-Content-Type-Options отдаются `nginx` для всех ответов.

## Шаг 2. Проверка

```bash
# Все сервисы healthy
docker compose -f docker-compose.prod.yml ps

# HTTPS отвечает
curl -I https://your-real-domain.com/healthz

# Логи certbot — auto-renew работает
docker compose -f docker-compose.prod.yml logs certbot

# Проверка SSL-рейтинга — https://www.ssllabs.com/ssltest/?d=your-real-domain.com
# Должно быть A или A+ при текущих ssl_protocols и HSTS
```

## Регулярные операции

| Действие | Команда |
|---|---|
| Логи backend | `docker compose -f docker-compose.prod.yml logs -f backend` |
| Применить миграцию | `docker compose -f docker-compose.prod.yml exec backend python manage.py migrate` |
| Создать суперюзера | `docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser` |
| Восстановить из бэкапа | `gunzip -c ./backups/backup_2026-05-22_120000.sql.gz \| docker compose -f docker-compose.prod.yml exec -T db psql -U $POSTGRES_USER $POSTGRES_DB` |
| Проверить срок сертификата | `docker compose -f docker-compose.prod.yml run --rm certbot certificates` |
| Принудительно обновить TLS | `docker compose -f docker-compose.prod.yml run --rm certbot renew --force-renewal && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload` |

## Откат

```bash
# Остановить
docker compose -f docker-compose.prod.yml down

# Полный сброс (ОСТОРОЖНО — снесёт БД и сертификаты)
docker compose -f docker-compose.prod.yml down -v
rm -rf ./certbot ./backups
```
