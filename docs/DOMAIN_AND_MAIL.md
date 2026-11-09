# Свой домен и почта: инструкция на потом

Сейчас сайт работает на бесплатных адресах: фронтенд `https://diplom-work-main-frontend.vercel.app`, API
`https://diplom-work-main-production.up.railway.app`. Письма (подтверждение почты, сброс пароля) не уходят,
пока не настроен Resend. Ниже — что сделать, когда дойдут руки. Порядок важен: домен → сайт → API → почта.

## 0. Найти, где куплен домен

- Поиск в почте: «rpgacademy», «domain», «домен», «счёт», «invoice». В письме будет регистратор (например,
  ps.kz, hoster.kz, Namecheap, GoDaddy, Cloudflare, REG.RU) и вход в его кабинет.
- Или проверка WHOIS: whois.com → `rpgacademy.org`. В поле **Registrar** — регистратор, в **Expiry date** —
  до какого числа оплачен. Если WHOIS пишет, что домен свободен, — он не куплен или истёк.
- Сейчас адрес `rpgacademy.org` не открывается: у домена нет DNS-записей (или он не оплачен).

Дальше все DNS-записи добавляются в кабинете регистратора, раздел «DNS», «Управление зоной» или «DNS records».
Записи начинают работать через 5–60 минут (иногда до суток).

## 1. Сайт на своём домене (Vercel)

1. Vercel → проект `rpgacademy` (тот, у которого адрес `diplom-work-main-frontend.vercel.app`) → **Settings →
   Domains** → добавить `rpgacademy.org` и `www.rpgacademy.org`.
2. Vercel покажет нужные записи. Обычно это `A` для `@` → `76.76.21.21` и `CNAME` для `www` →
   `cname.vercel-dns.com`. Добавить их у регистратора **ровно так, как показывает Vercel**.
3. Дождаться зелёной галочки у домена в Vercel (сертификат HTTPS Vercel выпустит сам).

Старый адрес `diplom-work-main-frontend.vercel.app` продолжит работать.

## 2. API на своём поддомене (Railway)

1. Railway → сервис бэкенда → **Settings → Networking → Custom Domain** → `api.rpgacademy.org`.
2. Railway покажет `CNAME` (вида `xxxx.up.railway.app`) → добавить у регистратора запись `CNAME` для `api`.
3. Railway → **Variables** (после сохранения сервис перезапустится сам):
   - `ALLOWED_HOSTS` — дописать через запятую `api.rpgacademy.org` (без `https://`);
   - `FRONTEND_URL=https://rpgacademy.org` (на неё ведут ссылки из писем; адрес сам попадёт в CORS);
   - `CORS_ALLOWED_ORIGINS=https://www.rpgacademy.org`;
   - `CSRF_TRUSTED_ORIGINS=https://api.rpgacademy.org` (для входа в админку по новому адресу).
4. Vercel → **Settings → Environment Variables** → `NEXT_PUBLIC_API_BASE=https://api.rpgacademy.org/api` →
   **Redeploy** (значение вшивается при сборке). Запуск кода (WebSocket) пойдёт на тот же адрес сам.

Проверка: открыть `https://rpgacademy.org`, войти, решить шаг с кодом.

## 3. Почта для писем сайта (Resend)

Railway не пропускает SMTP, поэтому сайт отправляет письма через Resend (HTTP API, бесплатно до 3000 писем в
месяц и 100 в день). Без своего домена Resend шлёт только на почту владельца аккаунта, поэтому сначала
нужен шаг 0.

1. resend.com → регистрация → **Domains → Add Domain** → `rpgacademy.org`.
2. Resend покажет 3–4 записи (DKIM `TXT` вида `resend._domainkey`, SPF `TXT` и `MX` на поддомене `send`).
   Добавить их у регистратора как есть → **Verify**.
3. **API Keys → Create API Key** (права Sending access) → скопировать ключ (показывается один раз).
4. Railway → Variables:
   - `RESEND_API_KEY=<ключ>` — бэкенд сам переключится с «писем в консоль» на Resend;
   - `DEFAULT_FROM_EMAIL=RPG Academy <noreply@rpgacademy.org>`.
5. Когда письма пошли, можно включить: `TEACHER_REQUIRE_EMAIL=1` (преподаватель подтверждает почту) и, если
   нужна регистрация преподавателей без кода, `TEACHER_SELF_REGISTRATION=1`.

Проверка: зарегистрироваться с настоящей почтой → письмо пришло; в Resend → **Logs** видна отправка.
`python manage.py pilot_check` перестанет предупреждать о `EMAIL_BACKEND=console`.

**Если вы купили ящик для домена** (Яндекс 360, Zoho, Google Workspace) — это почта для *получения* писем на
`...@rpgacademy.org`. Его записи `MX` стоят на самом домене, а записи Resend — на поддомене `send`, поэтому они
не мешают друг другу. Существующие `MX` и `TXT` ящика не удалять.

## Что не трогать

- `DJANGO_SECRET_KEY`, `ANALYTICS_EXPORT_SALT`, `DATABASE_URL` — от домена не зависят.
- Свой `TEACHER_INVITE_CODE` остаётся как есть.
