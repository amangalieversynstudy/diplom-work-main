# RPG Learning Platform (Django + Next.js)

![pipeline status](https://gitlab.com/amangalieversynstudy/diplom-work/badges/main/pipeline.svg)
![coverage](https://gitlab.com/amangalieversynstudy/diplom-work/badges/main/coverage.svg)
![codecov](https://codecov.io/gh/amangalieversynstudy/diplom-work/branch/main/graph/badge.svg)

— Быстрый старт: [локально](README.deploy.md#quickstart-local) • [staging](README.deploy.md#quickstart-staging) • [Полный гайд по деплою](README.deploy.md)
— CI/CD на GitLab: [docs/gitlab.md](docs/gitlab.md) описывает пайплайн, переменные и чек-листы.

## Что уже реализовано

- **Аутентификация и профиль**: регистрация/логин, JWT, выбор класса героя, XP/уровень, таблица лидеров.
- **Миры и миссии**: треки → миры → миссии с координатами, prerequisite-ами и цепочками Story → Quiz → Code.
- **Runner для кода**: локальный `/api/runner/execute` проверяет решения и пишет TaskProgress.
- **Фоновые задачи**: Celery воркер, Redis как брокер, подготовка к отложенным начислениям и уведомлениям.
- **Демо-контент**: management-команды `load_demo_content`, `create_demo_superuser`, `print_demo_summary` заполняют базу и создают логин `admin/admin123`.

## Почему Docker обязателен

- Один `docker compose up -d db redis backend frontend` поднимает Postgres, Redis, Django, Next.js и Celery в согласованных версиях.
- Локальная разработка и CI получают идентичные артефакты; баги «работает у меня» исчезают.
- Seed-скрипты и миграции гоняются внутри контейнера: `docker compose exec backend python manage.py load_demo_content` и т.д.
- Конфигурация легко переносится на staging/production: те же образы и `docker-compose.yml`.

## Структура репозитория

| Папка/файл                  | Назначение                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------- |
| `backend/`                  | Django/DRF проект (`core`, `users`, `game`, Celery, management-команды).           |
| `frontend/`                 | Next.js + Tailwind UI, страницы `/worlds`, `/missions`, `/profile`.                |
| `docker-compose.yml`        | Локальный стек: db/redis/backend/frontend/celery.                                  |
| `docs/`                     | Живые гайды: `gitlab.md`, `file_overview.md`, `janitore_instructions.txt`, отчёты. |
| `diagnostics/postman/`      | Коллекции/окружения для ручного теста API.                                         |
| `ci/`, `.github/workflows/` | Сценарии GitLab/GitHub CI.                                                         |
| `Makefile`                  | Укороченные команды (`deploy-local`, `seed-demo`, `logs`).                         |

Подробные описания файлов лежат в `docs/file_overview.md`, но этот README теперь даёт быстрый обзор, что где искать.

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
- [GitLab CI/CD](#gitlab-cicd)
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

## Manual testing (локально)

Two reliable flows:

1. Full Docker (если front-контейнер стабильно читает volume на вашей системе):

```bash
docker compose up -d db redis backend frontend
docker compose exec backend python manage.py load_demo_content
# Backend API index
open http://localhost:8000/api
# Frontend (Next.js dev)
open http://localhost:3000/worlds
```

2. Надёжный для macOS: backend в Docker, frontend локально (обходит volume error -35):

```bash
# Backend
docker compose up -d db redis backend
docker compose exec backend python manage.py load_demo_content

# Frontend (локально)
cd frontend
echo "NEXT_PUBLIC_API_BASE=http://localhost:8000/api" > .env.local
npm install --no-audit --no-fund
npm run dev -- -p 3002 -H 127.0.0.1
# Открыть UI
open http://127.0.0.1:3002/worlds
```

Checklist:

- Register → Login (username+password)
- /class → выбрать класс
- /worlds → острова и прогресс
- /worlds/1 → карта нод из бэкенда (pos_x/pos_y)
- /missions/{id} → Start/Complete, XP начисляется; Gate недоступна до Intro

Если просто нужен индекс API: http://localhost:8000/api

## Механика урока (Story → Quiz → Code)

Новая страница миссии повторяет привычный цикл CodeCombat:

- **Степпер** показывает 3 шага (теория → викторина → код) и тянет данные из `/api/mission-tasks/?mission=<id>`. Для каждого шага видны XP, длительность и тип задания.
- **Синхронизация прогресса** происходит через `/api/task-progress/`: любые действия (прочитать, выбрать ответ, прогнать код) сразу создают/обновляют запись TaskProgress и отображают attempts/best_score.
- **Код-раннер** отправляет код в локальный `POST /api/runner/execute`, который проверяет ожидаемый сниппет и возвращает stdout/tests. Успешный прогон автоматически отмечает шаг как `completed` и начисляет XP миссии.
- **Фейковый платёжный поток** закрывает премиум-задачи. Кнопка «Открыть премиум» вызывает `POST /api/payments/checkout`, эмитирует intent и снимает блокировку шага.

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

Проект: обучающая RPG-платформа (аналог CodeCombat), цель — вырастить пользователя до Junior Django Developer.

Стек:

- Backend: Django + Django REST Framework, JWT, PostgreSQL, Celery + Redis
- Frontend: Next.js (React) + Tailwind CSS
- Payments: Stripe
- DevOps: Docker, docker-compose, GitHub Actions, Render/Railway/AWS для деплоя

Структура репозитория:

- /backend — Django проект
- /frontend — Next.js приложение
- docker-compose.yml — локальный стек: db, redis, backend, frontend, celery
- .github/workflows — CI

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

## GitLab CI/CD

- **Конфигурация** — хранится в `.gitlab-ci.yml`. Структура: `lint → test → frontend → build → smoke → deploy`.
- **Docker job-ы** (`backend-build-image`, `smoke-backend-image`, `deploy-local`) используют сервис `docker:dind`. На GitLab.com shared runner-ах флаг `privileged` отключён, поэтому подключаемся к демону через `DOCKER_HOST=tcp://docker:2375` и выключаем TLS (`DOCKER_TLS_CERTDIR=""`).
- **Отчёты** — `backend-test` публикует `pytest` результаты и coverage, фронтенд-джобы сохраняют `.next` как артефакт.
- **Документация** — см. `docs/gitlab.md` для детального описания стадий, переменных, чек-листа перед merge и типовых ошибок (`lookup docker`, `healthz`).

Когда обновляешь `.gitlab-ci.yml`, обязательно синхронизируй заметки в `docs/gitlab.md`, чтобы команда видела единое место правды.

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
