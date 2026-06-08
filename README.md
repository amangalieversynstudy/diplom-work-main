# RPG Learning Platform (Django + Next.js)

— Быстрый старт: [локально](README.deploy.md#quickstart-local) • [staging](README.deploy.md#quickstart-staging) • [Полный гайд по деплою](README.deploy.md)
— CI: GitHub Actions — `.github/workflows/ci.yml` (бэкенд: pytest, фронтенд: build).

## Что реализовано

### Аутентификация и профиль
- Регистрация / логин / JWT (access + refresh), смена пароля
- Email-верификация: письмо при регистрации, `user.is_active=False` до подтверждения
- Email через **Resend HTTP API** (`django-anymail[resend]`) — Railway блокирует SMTP egress
- Профиль: XP, уровень, класс героя (Mage / Knight), инвентарь
- Выбор класса **заблокирован** до прохождения вводного курса (`Track.is_intro=True`)
- Лидерборд: фильтры по периодам (all_time / weekly / monthly), топ-200

### Геймплей
- Треки → Локации (карта мира) → Миссии → Задачи (Story → Quiz → Code)
- **Вводный курс "Основы Python"** (`backend/game/fixtures/intro_course.json`):
  4 миссии × 3 задачи = 12 шагов с реальным учебным контентом RU/EN
- **Sequential unlock** — Mission 2 разблокируется только после Mission 1, и т.д.
  (поле `prerequisites` в `Mission`, проверка в `MissionSerializer.get_available()`)
- Карты миров визуально меняются по классу игрока (`AdventureMap.jsx`)
- Прогресс синхронизируется через `/api/task-progress/`; attempts, best_score, статус
- Адаптивный layout страницы миссии: ≥1280px — 3 колонки, иначе стек по вертикали

### Стриминговый терминал (Phase 4)
- xterm.js + WebSocket (`ws://host/ws/runner/?token=<JWT>`)
- Код выполняется в **Docker-песочнице** `python:3.11-alpine` (128MB RAM, 64 PID, no-network, 15s timeout)
- Лимит вывода 50 KB — после `[ВЫВОД ОБРЕЗАН]`
- Каждая строка stdout/stderr транслируется в реальном времени
- Кнопка Stop убивает контейнер через cooperative stop-event
- **Subprocess fallback** — если Docker недоступен (например, Railway без Docker-in-Docker), runner переходит на `subprocess.Popen`. Без песочницы, но рабочий для demo/защиты
- **Resizable** — высота терминала перетаскивается (150–1000px, default 550px)

### AI-ассистент
- Кнопка "AI Summon" в редакторе → POST `/api/ai-assist/` (бэкенд сам списывает `ai_summons`)
- Модель: **Gemini 2.5 Flash** через новый SDK `google-genai` (API `v1`)
- Конфиг: `GEMINI_API_KEY` обязателен; `GEMINI_MODEL` опционален (default — `gemini-2.5-flash`)
- `max_output_tokens=2048` — учитывает thinking-токены Gemini 2.5
- Rate-limit: DRF `ai_assist` — 10 запросов/мин/пользователь → 429
- Word-wrap вывода (70 символов) — длинные подсказки не обрезаются в xterm
- Graceful fallback: без ключа или при квоте выводит сообщение в терминал

### Инвентарь (3 предмета)
| Предмет | Действие |
|---|---|
| 🏗 Свиток Архитектора | Вставляет boilerplate-каркас кода |
| 💡 Зелье Ясности | Показывает подсказку из `task.data.hint` |
| 🤖 AI Summon | Вызывает Gemini для анализа кода |

### Локализация
- Русский / Английский через кастомный React Context
- Мгновенное переключение без перезагрузки, сохранение в localStorage
- Словари: `frontend/dictionaries/en.js` + `frontend/dictionaries/ru.js`

### Инфраструктура
- **Daphne (ASGI)** обслуживает HTTP и WebSocket в одном процессе (был gunicorn — переехали из-за WS)
- Django Channels 4 + InMemoryChannelLayer для WS-роутинга
- Docker Compose локально: PostgreSQL + Daphne + Next.js
- **Production деплой**:
  - Backend → **Railway** (`Dockerfile.backend` + `railway.toml`, миграции + collectstatic + loaddata в startCommand)
  - Frontend → **Vercel** (Next.js, `NEXT_PUBLIC_API_BASE` указывает на Railway-домен)
  - Email → **Resend** (HTTP API, SMTP закрыт на Railway)
- Celery + Redis: фоновые задачи (опционально)
- 26 pytest-тестов включая async WebSocket-тесты через `WebsocketCommunicator`

### Django Admin (CMS для методологов)
- Редактирование курсов без кода: fieldsets RU/EN, stacked inline задач
- Цветные badges по типу задачи (story/quiz/code)
- `list_editable` для быстрой правки порядка и XP
- Поиск + фильтры на всех моделях

## Почему Docker обязателен

- Один `docker compose up --build` поднимает Postgres, Daphne (ASGI), Next.js и опционально Redis+Celery.
- Код-раннер **требует Docker** на хосте: `stream_python_code()` создаёт контейнер `python:3.11-alpine` для каждого запуска.
- Локальная разработка и CI получают идентичные артефакты; баги «работает у меня» исчезают.
- Seed-скрипты и миграции гоняются внутри контейнера: `docker compose exec backend python manage.py migrate` и т.д.
- Конфигурация легко переносится на staging/production: те же образы и `docker-compose.yml`.

## Структура репозитория

| Папка/файл | Назначение |
|---|---|
| `backend/` | Django/DRF + Channels + Daphne (`core`, `users`, `game`) |
| `backend/game/fixtures/intro_course.json` | Данные вводного курса Python (Track+Location+4 Missions+12 Tasks) |
| `backend/game/runner.py` | Docker-песочница — `stream_python_code()` генератор событий |
| `backend/game/consumers.py` | WebSocket consumer — стриминг через asyncio + threading |
| `frontend/` | Next.js 14 + Tailwind; страницы `/worlds`, `/missions`, `/profile` |
| `frontend/components/Terminal.jsx` | xterm.js обёртка (SSR-safe, динамический import) |
| `frontend/components/CodeRunnerPanel.jsx` | Редактор + терминал + инвентарь + AI Summon |
| `frontend/dictionaries/` | i18n словари `en.js` и `ru.js` |
| `docker-compose.yml` | Локальный стек: db / backend (Daphne) / frontend |
| `README.deploy.md` | Полный гайд по деплою на VPS (nginx + SSL + systemd) |
| `.github/workflows/ci.yml` | CI: бэкенд (pytest) + фронтенд (build) |
| `Makefile` | Укороченные команды (`deploy-local`, `seed-demo`, `logs`) |

Быстрый просмотр фронтенда (без бэкенда):

```bash
cd frontend && npm ci --no-audit --no-fund && npm run dev
# если порт 3000 занят: npm run dev -- -p 3002 -H 127.0.0.1
```

Откройте http://localhost:3000 (или http://127.0.0.1:3002). По умолчанию фронтенд использует встроенный mock API по пути /api.

> Документация по деплою: см. `README.deploy.md` — там описаны deploy-local, deploy-staging, флаги DEMO_SEED/ALLOW_DEMO_SEED и Postman-инструкции.

> Примечание: когда переходите к работе с кодом, используйте удобные make-цели и .env — см. раздел [Make команды и .env](README.deploy.md#make-команды-и-env).

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

Содержание

- [Как начать с Make](#%D0%9A%D0%B0%D0%BA-%D0%BD%D0%B0%D1%87%D0%B0%D1%82%D1%8C-%D1%81-make)
- [Manual testing (локально)](#manual-testing-%D0%BB%D0%BE%D0%BA%D0%B0%D0%BB%D1%8C%D0%BD%D0%BE)
- [Быстрый старт](#%D0%91%D1%8B%D1%81%D1%82%D1%80%D1%8B%D0%B9-%D1%81%D1%82%D0%B0%D1%80%D1%82)
- [Codecov integration](#codecov-integration)
- [Документация по деплою](#%D0%94%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D0%B0%D1%86%D0%B8%D1%8F-%D0%BF%D0%BE-%D0%B4%D0%B5%D0%BF%D0%BB%D0%BE%D1%8E)
- [Manual testing (локально)](#manual-testing-%D0%BB%D0%BE%D0%BA%D0%B0%D0%BB%D1%8C%D0%BD%D0%BE-1)
- [CI (GitHub Actions)](#ci-github-actions)
- [Branch Protection](#branch-protection)
  - [Настройка защиты веток](#%D0%9D%D0%B0%D1%81%D1%82%D1%80%D0%BE%D0%B9%D0%BA%D0%B0-%D0%B7%D0%B0%D1%89%D0%B8%D1%82%D1%8B-%D0%B2%D0%B5%D1%82%D0%BE%D0%BA)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Как начать с Make

Быстрый локальный запуск без захода в подробный гайд:

```bash
[ -f .env ] || cp .env.example .env   # создать .env, если его нет
make deploy-local                      # поднять Redis+Postgres+Backend+Celery и засеять демо
make logs                              # смотреть логи бэкенда; Ctrl+C чтобы выйти
# make stop-local                       # остановить локальный стек (по необходимости)
```

## Быстрый старт через Docker Compose

Если не хотите использовать `make`, поднимите весь стек одной командой:

```bash
cd diplom-work
docker compose up -d db redis backend frontend
```

После запуска:

- `http://127.0.0.1:8000/healthz` — health-check бэкенда (должен вернуть `{ "status": "ok" }`).
- `http://127.0.0.1:3000` — Next.js UI, уже настроенный на API (`NEXT_PUBLIC_API_BASE=http://localhost:8000/api`).

Полезные команды:

```bash
docker compose ps          # статус контейнеров
docker compose logs -f backend  # логи Django
docker compose logs -f frontend # логи Next.js
docker compose down        # остановить все сервисы
```

> Если порты 8000/3000 заняты, остановите старые контейнеры (`docker ps` → `docker stop <name>`), затем повторите запуск.

## Быстрый старт (первый запуск)

```bash
# 1. Клонировать и настроить .env
git clone git@gitlab.com:amangalieversynstudy/diplom-work.git && cd diplom-work
cp .env.example .env
# Заполни .env: DJANGO_SECRET_KEY, DB_PASSWORD, GEMINI_API_KEY (опционально)

# 2. Поднять стек
docker compose up --build -d

# 3. Применить миграции + загрузить вводный курс
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py loaddata intro_course.json
docker compose exec backend python manage.py collectstatic --no-input
docker compose exec backend python manage.py createsuperuser

# 4. Открыть
open http://localhost:3000        # UI
open http://localhost:8000/api    # API Browser
open http://localhost:8000/admin  # Django Admin
```

## Локальная разработка (macOS — без контейнера фронтенда)

```bash
# Backend в Docker
docker compose up -d db backend

# Frontend локально (обходит volume error -35 на macOS)
cd frontend
echo "NEXT_PUBLIC_API_BASE=http://localhost:8000/api" > .env.local
npm install
npm run dev
open http://localhost:3000
```

## Ключевые API-эндпоинты

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/auth/register/` | Регистрация (письмо активации) |
| POST | `/api/auth/login/` | Логин → JWT tokens |
| GET | `/api/auth/verify/<uuid>/` | Активация email |
| POST | `/api/auth/resend-verify/` | Повторное письмо |
| GET | `/api/profile/me/` | Профиль + инвентарь |
| PATCH | `/api/profile/me/` | Обновление профиля |
| POST | `/api/profile/use-item/` | Расход предмета инвентаря |
| GET | `/api/game/intro-status/` | Статус вводного курса (class_unlocked) |
| POST | `/api/ai-assist/` | Gemini 2.5 Flash hint (10 req/min, списывает `ai_summons`) |
| WS | `ws://host/ws/runner/?token=JWT` | Стриминговый Python-раннер |
| GET | `/api/game/missions/` | Список миссий |
| POST | `/api/game/missions/{id}/complete/` | Завершить миссию + XP |
| GET | `/api/game/leaderboard/` | Лидерборд |

> Полный интерактивный список: `http://localhost:8000/swagger/`

## Запуск тестов

```bash
# Все тесты (26 pytest, включая async WebSocket-тесты)
DJANGO_SETTINGS_MODULE=core.settings.test PYTHONPATH=backend pytest --tb=short

# Frontend lint + build
cd frontend && npm run lint && npm run build
```

## Механика урока (Story → Quiz → Code)

Новая страница миссии повторяет привычный цикл CodeCombat:

- **Степпер** показывает 3 шага (теория → викторина → код) и тянет данные из `/api/mission-tasks/?mission=<id>`. Для каждого шага видны XP, длительность и тип задания.
- **Синхронизация прогресса** происходит через `/api/task-progress/`: любые действия (прочитать, выбрать ответ, прогнать код) сразу создают/обновляют запись TaskProgress и отображают attempts/best_score.
- **Код-раннер** подключается через WebSocket `/ws/runner/?token=<JWT>` и стримит stdout/stderr из Docker-песочницы в xterm.js построчно. На `exit code 0` шаг автоматически отмечается `completed`, начисляется XP. При недоступности Docker задействуется subprocess-fallback.
- **AI-Мудрец** доступен в редакторе (`/api/ai-assist/`): тратит 1 `ai_summons` из инвентаря, возвращает подсказку от Gemini 2.5 Flash с учётом текущего кода и описания задачи.

Чтобы пощупать механику:

1. Засейте демо-контент: `docker compose exec backend python manage.py load_demo_content`.
2. Авторизуйтесь, откройте `/missions/1` и проходите шаги по очереди (Story/Quiz/Code). Каждый шаг сразу пишет TaskProgress, что видно после перезагрузки.
3. Зайдите на `/leaderboard` — таблица теперь использует `/api/leaderboard/` + фильтры по охвату/трекам/периоду. Если данных пока нет, быстро создайте пару записей `LeaderboardEntry` через Django admin.

=======

## Быстрый старт

- Локально: [README.deploy.md#quickstart-local](README.deploy.md#quickstart-local)
- Staging: [README.deploy.md#quickstart-staging](README.deploy.md#quickstart-staging)

Run backend tests with coverage locally (using Docker Compose):

```bash
# start DB and Redis
docker compose up -d db redis
# run tests inside backend container
docker compose exec backend pytest --cov=backend --cov-report=term-missing
```

CI stores `backend/coverage.xml` and `backend/pytest-results.xml` as job artifacts.

## Codecov integration

If you want a robust coverage badge, integrate Codecov. The CI now uploads `backend/coverage.xml` to Codecov when available. To enable upload for private repos, add `CODECOV_TOKEN` to your GitLab CI/CD variables (Project Settings → CI/CD → Variables).

After enabling Codecov and adding the token (if needed), add the Codecov badge URL to the README (placeholder added above).

Проект: обучающая RPG-платформа (вдохновлена CodeCombat) — дипломная работа.
Цель — снизить порог входа в Python через игровую механику (миссии-свитки, XP, инвентарь).

**Актуальный стек** (полное описание выше в README):
- Backend: Django 4.2 + DRF + Channels 4 (ASGI/Daphne), JWT, PostgreSQL
- Frontend: Next.js + Tailwind + xterm.js
- AI: Gemini 2.5 Flash через `google-genai` SDK
- Email: Resend HTTP API (`django-anymail`)
- Code Runner: Docker `python:3.11-alpine` sandbox + subprocess fallback
- DevOps: Docker Compose локально; **Railway** (backend) + **Vercel** (frontend) в production

## Документация по деплою

Подробный гайд по деплою (локально и staging), настройке раннера/хоста и авто-заливке демо-данных — в `README.deploy.md`.

Дальнейшие шаги см. TODOs в .github/ or project board

## Manual testing (локально)

Ниже шаги для ручного тестирования API и проверки состояния БД/Redis через Docker Compose (macOS, zsh).

1. Поднять сервисы (бэкенд)

```bash
# поднять все сервисы (db, redis, backend, celery)
docker compose up -d db redis backend celery

# или поднять только db и redis если backend не нужен
docker compose up -d db redis
```

2. Проверить статус контейнеров

```bash
docker compose ps
```

3. Создать суперпользователя (Django admin)

```bash
docker compose exec backend python manage.py createsuperuser
# или non-interactive (пример):
docker compose exec backend python manage.py createsuperuser --noinput --username admin --email admin@example.com || true
docker compose exec backend python manage.py shell -c "from django.contrib.auth import get_user_model; u=get_user_model().objects.get(username='admin'); u.set_password('adminpass'); u.save()"
```

Admin: http://localhost:8000/admin (логин: admin / пароль: adminpass)

Фронтенд: отдельным процессом

```bash
cd frontend && npm run dev
# если нужно, задайте адрес бэкенда: echo "NEXT_PUBLIC_API_BASE=http://localhost:8000/api" > .env.local
```

4. Примеры API-запросов (Postman / curl)

- Регистрация (POST)
  - URL: http://localhost:8000/api/auth/register/
  - Body (JSON):
    {
    "username": "test1",
    "password": "pass123",
    "email": "test1@example.com"
    }

- Логин (POST)
  - URL: http://localhost:8000/api/auth/login/
  - Body (JSON):
    {
    "username": "test1",
    "password": "pass123"
    }
  - Ответ: access + refresh токены

- Профиль (GET/PATCH)
  - URL: http://localhost:8000/api/profile
  - Header: Authorization: Bearer <access_token>
  - GET возвращает XP/level/bio/class_role
  - PATCH позволяет обновить bio и выбрать class_role (только один раз; сброс или повторный выбор другого класса вернёт 400)

- Получить профиль (GET)
  - URL: http://localhost:8000/api/auth/me/
  - Header: Authorization: Bearer <access_token>

5. Проверить данные в Postgres

```bash
# зайти в psql внутри контейнера
docker compose exec db psql -U rpguser -d rpgdb
# или выполнить SQL команду напрямую
docker compose exec db psql -U rpguser -d rpgdb -c "SELECT id, username, email FROM users_user;"
docker compose exec db psql -U rpguser -d rpgdb -c "SELECT id, user_id, xp, level FROM users_profile;"
```

6. Проверить Redis

```bash
docker compose exec redis redis-cli
# в интерактивной консоли: KEYS *
```

7. Статические файлы (если админ без стилей)

```bash
# собрать статику внутри контейнера (если не собрана автоматически)
docker compose exec backend python manage.py collectstatic --noinput
# при необходимости пересоберите образ:
docker compose build backend
docker compose up -d backend
```

8. Логи для отладки

```bash
docker compose logs -f backend
docker compose logs -f celery
```

9. Экспорт/дамп базы

```bash
docker compose exec db pg_dump -U rpguser rpgdb > db-dump.sql
```

Если хотите, могу сгенерировать пример Postman коллекции (JSON) или добавить конкретные curl-примеры для каждого endpoint.

## CI (GitHub Actions)

- **Конфигурация** — `.github/workflows/ci.yml`. Три job-а: `backend` (Postgres+Redis → миграции → `pytest` → `manage.py check --deploy`), `frontend` (`npm ci` → lint → `npm run build`), `security` (pip-audit + npm audit на PR).
- Триггеры: push и pull request в `main`.

## Branch Protection

Для обеспечения стабильности и безопасности кода, рекомендуется настроить защиту веток в вашем репозитории. Это поможет предотвратить случайные изменения в основной ветке и обеспечит, что все изменения проходят через процесс проверки.

### Настройка защиты веток

1. Перейдите в настройки вашего репозитория на GitHub.
2. Выберите вкладку "Branches".
3. В разделе "Branch protection rules" нажмите "Add rule".
4. Укажите имя ветки, которую хотите защитить (например, `main`).
5. Установите необходимые параметры защиты, такие как:
   - Требовать проверки статуса перед слиянием
   - Требовать, чтобы все проверки прошли
   - Запретить слияние, если есть конфликты
6. Нажмите "Create" для сохранения правил защиты ветки.
