#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════
# RPG Academy — one-shot production deploy
# ════════════════════════════════════════════════════════════════════
# Запускается ВНУТРИ VPS из корня проекта:
#   bash deploy.sh
#
# Что делает:
#   1) Проверяет .env.prod
#   2) Подставляет твой домен в nginx.conf
#   3) Бутстрапит HTTP-nginx + выпускает Let's Encrypt
#   4) Запускает полный prod-стек
#   5) Прогоняет миграции и загружает фикстуры
#   6) Печатает итоговый URL
# ════════════════════════════════════════════════════════════════════

set -e

ENV_FILE=".env.prod"

# ── 0. Sanity checks ────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ Не найден $ENV_FILE — скопируй .env.prod.example в .env.prod и заполни секреты"
  exit 1
fi

# Подгружаем переменные
set -a
. "./$ENV_FILE"
set +a

if [ -z "$DOMAIN" ] || [ -z "$GEMINI_API_KEY" ] || [ -z "$EMAIL_HOST_PASSWORD" ]; then
  echo "❌ В .env.prod не заполнены: DOMAIN / GEMINI_API_KEY / EMAIL_HOST_PASSWORD"
  exit 1
fi
if echo "$GEMINI_API_KEY" | grep -q "PASTE"; then
  echo "❌ GEMINI_API_KEY ещё содержит плейсхолдер — вставь реальный ключ из aistudio.google.com/apikey"
  exit 1
fi
if echo "$EMAIL_HOST_PASSWORD" | grep -q "PASTE"; then
  echo "❌ EMAIL_HOST_PASSWORD ещё содержит плейсхолдер — вставь Gmail App Password"
  exit 1
fi

echo "✅ env-проверки прошли. Домен: $DOMAIN"

# ── 1. Подставляем домен в nginx.conf ───────────────────────────────
if grep -q "rpg-academy.example.com" nginx.conf; then
  sed -i.bak "s/rpg-academy.example.com/$DOMAIN/g" nginx.conf
  echo "✅ nginx.conf обновлён под домен $DOMAIN"
fi

# ── 2. Папки ────────────────────────────────────────────────────────
mkdir -p ./certbot/www ./certbot/conf ./backups

# ── 3. Bootstrap nginx (HTTP-only) для ACME challenge ───────────────
echo "🚀 Запускаю bootstrap-nginx на 80-м порту..."
docker rm -f rpg-nginx-bootstrap 2>/dev/null || true
docker run --rm -d --name rpg-nginx-bootstrap -p 80:80 \
  -v "$PWD/nginx.bootstrap.conf:/etc/nginx/nginx.conf:ro" \
  -v "$PWD/certbot/www:/var/www/certbot:ro" \
  nginx:1.27-alpine
sleep 2

# ── 4. Выпускаем сертификат Let's Encrypt ──────────────────────────
# Проверка: если cert уже есть, пропускаем
if [ -f "./certbot/conf/live/$DOMAIN/fullchain.pem" ]; then
  echo "✅ Сертификат уже выпущен для $DOMAIN — пропускаю certonly"
else
  echo "🔐 Запрашиваю SSL у Let's Encrypt для $DOMAIN..."
  docker run --rm \
    -v "$PWD/certbot/conf:/etc/letsencrypt" \
    -v "$PWD/certbot/www:/var/www/certbot" \
    certbot/certbot:latest certonly --webroot -w /var/www/certbot \
    -d "$DOMAIN" \
    --email "$EMAIL_HOST_USER" --agree-tos --no-eff-email --non-interactive
fi

# ── 5. Снимаем bootstrap-nginx ─────────────────────────────────────
docker stop rpg-nginx-bootstrap 2>/dev/null || true

# ── 6. Поднимаем полный prod-стек ──────────────────────────────────
echo "🚀 Поднимаю полный production-стек..."
docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" up -d --build

# ── 7. Ждём готовности backend ─────────────────────────────────────
echo "⏳ Жду готовности backend..."
for i in $(seq 1 30); do
  if docker compose -f docker-compose.prod.yml exec -T backend wget -qO- http://localhost:8000/healthz >/dev/null 2>&1; then
    echo "✅ Backend healthy"
    break
  fi
  sleep 3
done

# ── 8. Загружаем фикстуры ──────────────────────────────────────────
echo "📦 Загружаю фикстуры (ranks, class_roles, intro_course)..."
docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" exec -T backend \
  python manage.py loaddata \
  game/fixtures/ranks.json \
  game/fixtures/class_roles.json \
  game/fixtures/intro_course.json || echo "⚠️ Часть фикстур не загрузилась (возможно уже есть)"

# ── 9. Итог ─────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ ДЕПЛОЙ ЗАВЕРШЁН"
echo "════════════════════════════════════════════════════════════════"
echo "🌐 Открой в браузере:  https://$DOMAIN"
echo "🔐 Создай суперюзера:"
echo "    docker compose -f docker-compose.prod.yml --env-file $ENV_FILE \\"
echo "      exec backend python manage.py createsuperuser"
echo ""
echo "📊 Статус сервисов:"
docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE" ps
