# Деплой — RPG Academy (Railway + Vercel)

Боевой стенд:

| Часть | Где | Как собирается |
|---|---|---|
| **Backend** (Django/DRF + WebSocket) | **Railway** | Docker из `Dockerfile.backend` (указан в `railway.toml`) |
| **PostgreSQL** | **Railway** (плагин) | даёт `DATABASE_URL` |
| **Redis** | **Railway** (плагин) | даёт `REDIS_URL` — кэш для throttling + Channels |
| **Frontend** (Next.js) | **Vercel** | `next build`, root = `frontend/` |

```
Браузер ── HTTPS ──► Vercel (Next.js)
   │                      │  REST /api  +  WebSocket /ws/runner
   └──────────────────────┴────────────► Railway: Django (Daphne) ─► Postgres / Redis
                                                         └─► Resend (письма), Judge0 (песочница)
```

Содержание: [Backend → Railway](#backend-railway) · [Frontend → Vercel](#frontend-vercel) · [Локально](#quickstart-local) · [Проверка](#проверка-после-деплоя) · [Частые проблемы](#частые-проблемы)

---

## <a id="backend-railway"></a>1. Backend → Railway

### 1.1. Сервис
1. Railway → **New Project → Deploy from GitHub repo** → выбери репозиторий.
2. Branch — рабочая ветка деплоя (**`feature/final-polish`**).
3. Railway увидит `railway.toml` и соберёт бэкенд по `Dockerfile.backend`. Менять builder не нужно.

`railway.toml` уже задаёт start-команду:
```
migrate → collectstatic → loaddata (ranks, class_roles, intro_course) → daphne (ASGI)
```
То есть при каждом деплое применяются миграции, собирается статика и подгружается курс.

### 1.2. Базы
- **Add → Database → PostgreSQL** → появится переменная `DATABASE_URL` (бэкенд её читает через `dj-database-url`).
- **Add → Database → Redis** → `REDIS_URL`. **Нужен**: DRF-throttling хранит счётчики в Redis-кэше; без него запросы будут падать на обращении к кэшу.
- В сервисе backend пробрось обе переменные (Variables → Reference на сервисы Postgres/Redis).

### 1.3. Переменные окружения (Variables)
| Переменная | Значение | Зачем |
|---|---|---|
| `DJANGO_SECRET_KEY` | длинная случайная строка | **обязательно** — прод не стартует с дефолтом |
| `DATABASE_URL` | из плагина Postgres | БД |
| `REDIS_URL` | из плагина Redis | кэш/throttling/Channels |
| `ALLOWED_HOSTS` | `*.up.railway.app,твой-домен` | хосты Django |
| `FRONTEND_URL` | `https://<проект>.vercel.app` | ссылки в письмах + CORS-fallback |
| `RESEND_API_KEY` | ключ Resend | реальная отправка писем (Railway блокирует SMTP) |
| `DEFAULT_FROM_EMAIL` | `noreply@твойдомен` | отправитель писем |
| `ENABLE_STREAK_SCHEDULER` | `1` | ежедневное письмо-напоминание о серии |
| `STREAK_REMINDER_HOUR` / `_MINUTE` | напр. `13` / `0` (UTC) | время рассылки (13:00 UTC = 18:00 Алматы) |
| `SENTRY_DSN` | (опц.) | мониторинг ошибок |
| `RUNNER_JUDGE0_URL` / `RUNNER_JUDGE0_KEY` | (опц.) | внешняя песочница для запуска кода |

> `DJANGO_SETTINGS_MODULE=core.settings.production` выставляется самой start-командой — отдельно задавать не нужно.

> **CORS:** прод автоматически разрешает домены вида `diplom-work-main*.vercel.app` (regex в `production.py`). Если имя Vercel-проекта другое — добавь `CORS_ALLOWED_ORIGINS=https://твой-фронт.vercel.app`. Для своего домена задай ещё `CSRF_TRUSTED_ORIGINS=https://твой-домен`.

### 1.4. Первый запуск
После успешного деплоя:
- Открой `https://<backend>.up.railway.app/healthz` → `{"status":"ok"}`.
- Создай админа: Railway → backend → **Run a command** (или CLI `railway run`): `python manage.py createsuperuser`.
- Зайди в `/admin/` (брендированная админка jazzmin) — там правится контент курсов.

### 1.5. Запуск кода учеников
На Railway нет Docker-in-Docker, поэтому код исполняется во внешней песочнице **Judge0** (`RUNNER_JUDGE0_URL`). Если Judge0 не задан/недоступен — срабатывает локальный subprocess-фолбэк (он захардён: без секретов, с rlimits). Чтобы запретить локальное исполнение, поставь `RUNNER_ALLOW_UNSAFE_FALLBACK=False`.

---

## <a id="frontend-vercel"></a>2. Frontend → Vercel

1. Vercel → **Add New → Project** → импортируй тот же репозиторий.
2. **Root Directory = `frontend`**, Framework = **Next.js** (определится сам).
3. Branch — та же `feature/final-polish`.
4. Переменная окружения:
   | Переменная | Значение |
   |---|---|
   | `NEXT_PUBLIC_API_BASE` | `https://<backend>.up.railway.app/api` |
5. Deploy. Vercel сам делает `next build`.

После деплоя фронт будет ходить в API на Railway; CORS уже настроен на стороне бэка (см. 1.3).

---

## <a id="quickstart-local"></a>3. Локальная разработка

**Вариант А — Docker-стек** (db + backend + frontend одной командой):
```bash
cp .env.example .env          # заполни при необходимости
docker compose up --build
# backend: http://localhost:8000 , frontend: http://localhost:3000
```

**Вариант Б — вручную:**
```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_SETTINGS_MODULE=core.settings.local
python manage.py migrate
python manage.py loaddata ranks class_roles intro_course
python manage.py runserver        # http://localhost:8000

# frontend (в другом терминале)
cd frontend && npm install
npm run dev                       # http://localhost:3000
```
Локально письма по умолчанию идут в консоль (`EMAIL_BACKEND=console`), запуск кода — через Docker-песочницу (если есть Docker) или Judge0/фолбэк.

---

## Проверка после деплоя
- `GET /healthz` → `{"status":"ok"}`.
- Регистрация → письмо активации (проверь Resend dashboard) → активация → вход.
- `/worlds` → пройти миссию (story/quiz/code) → начисление XP/серии.
- `/admin/` → создание/редактирование курса.
- Тесты/CI: `.github/workflows/ci.yml` (бэкенд `pytest`, фронт `npm run build`).

## Частые проблемы
| Симптом | Причина / решение |
|---|---|
| Прод не стартует, `ImproperlyConfigured` | не задан `DJANGO_SECRET_KEY` |
| 500 на любом API | нет `REDIS_URL` (throttling-кэш не работает) — добавь Redis-плагин |
| Письма не приходят | нет `RESEND_API_KEY`/`DEFAULT_FROM_EMAIL`, или домен не верифицирован в Resend |
| CORS-ошибка на фронте | имя Vercel-проекта не подпадает под regex — задай `CORS_ALLOWED_ORIGINS` |
| Запуск кода «недоступен» | задай `RUNNER_JUDGE0_URL` (+ ключ) или оставь фолбэк включённым |
| Письмо о серии не уходит | `ENABLE_STREAK_SCHEDULER=1` + время в UTC; проверь логи деплоя |

---

## (Опционально) Self-host на VPS
В репозитории остаётся альтернативный путь self-hosting: `deploy.sh` + `docker-compose.prod.yml` + `nginx.conf` (nginx + Let's Encrypt). Он независим от Railway/Vercel и при них не используется.
