#!/usr/bin/env bash
# DuckDNS IP-updater. Запускать раз в 5 минут через cron.
#
# Установка на VPS:
#   cp scripts/duckdns-update.sh /usr/local/bin/duckdns.sh
#   chmod +x /usr/local/bin/duckdns.sh
#   echo "DUCKDNS_TOKEN=<твой-токен-с-duckdns.org>" >> /etc/environment
#   echo "DUCKDNS_DOMAIN=rpg-academy" >> /etc/environment    # без .duckdns.org
#   crontab -e
#   */5 * * * * /usr/local/bin/duckdns.sh >> /var/log/duckdns.log 2>&1

: "${DUCKDNS_TOKEN:?env DUCKDNS_TOKEN not set}"
: "${DUCKDNS_DOMAIN:?env DUCKDNS_DOMAIN not set (без .duckdns.org)}"

response=$(curl -s "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=")
echo "$(date -Iseconds) DuckDNS update: $response"
