#!/usr/bin/env bash
# Первичный setup VPS под RPG Academy.
# Запускать на свежей Ubuntu 22.04 как root (или через sudo).
#
# Использование:
#   curl -fsSL https://raw.githubusercontent.com/<user>/diplom-work-main/main/deploy/setup_vps.sh | bash
# или клонировать репо и запустить:
#   bash deploy/setup_vps.sh

set -e

DOMAIN="${1:-my-domain.tld}"
REPO_URL="${2:-https://github.com/amangalieversynstudy/diplom-work-main.git}"

echo "==> Обновляю систему..."
apt-get update
apt-get upgrade -y

echo "==> Ставлю базовые пакеты..."
apt-get install -y curl git ufw nginx certbot python3-certbot-nginx

echo "==> Ставлю Docker..."
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

echo "==> Docker Compose plugin..."
apt-get install -y docker-compose-plugin

echo "==> Файрвол..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
echo "y" | ufw enable

echo "==> Клон репо..."
mkdir -p /opt
cd /opt
[ -d /opt/rpg-academy ] || git clone "$REPO_URL" rpg-academy
cd rpg-academy

echo "==> Копирую .env (нужно вручную заполнить!)..."
[ -f .env ] || cp .env.example .env

echo ""
echo "─────────────────────────────────────────────────────"
echo "Дальше — руками:"
echo ""
echo "  1. nano /opt/rpg-academy/.env"
echo "     Заполни: SECRET_KEY, POSTGRES_PASSWORD, EMAIL_*, GEMINI_API_KEY,"
echo "     FRONTEND_URL=https://$DOMAIN, ALLOWED_HOSTS=$DOMAIN"
echo ""
echo "  2. cp deploy/nginx.conf /etc/nginx/sites-available/rpg-academy"
echo "     sed -i \"s/my-domain.tld/$DOMAIN/g\" /etc/nginx/sites-available/rpg-academy"
echo "     ln -sf /etc/nginx/sites-available/rpg-academy /etc/nginx/sites-enabled/"
echo "     rm -f /etc/nginx/sites-enabled/default"
echo "     nginx -t && systemctl reload nginx"
echo ""
echo "  3. certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
echo "  4. cd /opt/rpg-academy"
echo "     docker compose up -d --build"
echo "     docker compose exec backend python manage.py migrate"
echo "     docker compose exec backend python manage.py loaddata intro_course"
echo "     docker compose exec backend python manage.py createsuperuser"
echo ""
echo "  5. Открой https://$DOMAIN — должна загрузиться главная."
echo "─────────────────────────────────────────────────────"
