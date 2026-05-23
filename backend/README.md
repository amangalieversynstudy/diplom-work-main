Backend: Django + DRF + Channels (ASGI/Daphne)

## Local run

1. Copy `.env.example` → `.env` and edit `DJANGO_SECRET_KEY`, DB creds, `GEMINI_API_KEY`
2. `docker compose up --build`
3. `docker compose exec backend python manage.py migrate`
4. `docker compose exec backend python manage.py loaddata ranks class_roles intro_course`

## Stack

- Django 4.2 + DRF, JWT via `djangorestframework-simplejwt`
- Channels 4 + Daphne (ASGI) — обслуживает HTTP и WebSocket в одном процессе
- PostgreSQL, Redis (опц.), Celery (опц.)
- Gemini 2.5 Flash via `google-genai` SDK (set `GEMINI_API_KEY`, optional `GEMINI_MODEL`)
- Email via Resend HTTP API (`django-anymail[resend]`)

## Core API

### Auth & Profile (`users/urls*.py`)
- `POST /api/auth/register/` — email verification on
- `POST /api/auth/jwt/create/` — login → access + refresh
- `POST /api/auth/jwt/refresh/`
- `GET  /api/profile/me/`, `PATCH /api/profile/me/`
- `POST /api/profile/use-item/` — расход предмета инвентаря

### Game (`game/urls.py`)
- `GET  /api/tracks/`, `/api/locations/`, `/api/missions/`
- `POST /api/missions/{id}/start/`, `/api/missions/{id}/complete/`
- `GET  /api/mission-tasks/?mission=<id>`
- `POST /api/task-progress/` (upsert by `(user, task)`)
- `GET  /api/leaderboard/?period=all_time|weekly|monthly`
- `GET  /api/ranks/`, `/api/progress/`

### Runner (sandbox)
- `POST /api/runner/execute/` — one-shot run, returns full output
- `WS   /ws/runner/?token=<JWT>` — streaming run via xterm.js
- Sandbox: Docker `python:3.11-alpine` (128MB / 64 PID / no-net / 15s)
- **Subprocess fallback** активируется автоматически если Docker недоступен (Railway)

### AI Assistant
- `POST /api/ai-assist/` — Gemini hint, 10 req/min, списывает `ai_summons`

### Misc
- `GET /api/intro-status/` — пройден ли вводный курс (для разблокировки класса)
- `GET /swagger/` — интерактивный API browser
- `GET /healthz` — health-check

## Tests

```bash
DJANGO_SETTINGS_MODULE=core.settings.test PYTHONPATH=backend pytest --tb=short
```

Includes async WebSocket tests via `channels.testing.WebsocketCommunicator`.

## Celery

```bash
celery -A core worker -l info
```
