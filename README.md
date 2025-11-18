# RPG Learning Platform (Django + Next.js)

![pipeline status](https://gitlab.com/amangalieversynstudy/diplom-work/badges/main/pipeline.svg)
![coverage](https://gitlab.com/amangalieversynstudy/diplom-work/badges/main/coverage.svg)
![codecov](https://codecov.io/gh/amangalieversynstudy/diplom-work/branch/main/graph/badge.svg)

— Быстрый старт: [локально](README.deploy.md#quickstart-local) • [staging](README.deploy.md#quickstart-staging) • [Полный гайд по деплою](README.deploy.md)

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

## Manual testing (локально)

Two reliable flows:

1) Full Docker (если front-контейнер стабильно читает volume на вашей системе):

```bash
docker compose up -d db redis backend frontend
docker compose exec backend python manage.py load_demo_content
# Backend API index
open http://localhost:8000/api
# Frontend (Next.js dev)
open http://localhost:3000/worlds
```

2) Надёжный для macOS: backend в Docker, frontend локально (обходит volume error -35):

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

Codecov integration
-------------------

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

Документация по деплою
----------------------

Подробный гайд по деплою (локально и staging), настройке раннера/хоста и авто-заливке демо-данных — в `README.deploy.md`.

Дальнейшие шаги см. TODOs в .github/ or project board

Manual testing (локально)
------------------------

Ниже шаги для ручного тестирования API и проверки состояния БД/Redis через Docker Compose (macOS, zsh).

1) Поднять сервисы (бэкенд)

```bash
# поднять все сервисы (db, redis, backend, celery)
docker compose up -d db redis backend celery

# или поднять только db и redis если backend не нужен
docker compose up -d db redis
```

2) Проверить статус контейнеров

```bash
docker compose ps
```

3) Создать суперпользователя (Django admin)

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

4) Примеры API-запросов (Postman / curl)

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

5) Проверить данные в Postgres

```bash
# зайти в psql внутри контейнера
docker compose exec db psql -U rpguser -d rpgdb
# или выполнить SQL команду напрямую
docker compose exec db psql -U rpguser -d rpgdb -c "SELECT id, username, email FROM users_user;"
docker compose exec db psql -U rpguser -d rpgdb -c "SELECT id, user_id, xp, level FROM users_profile;"
```

6) Проверить Redis

```bash
docker compose exec redis redis-cli
# в интерактивной консоли: KEYS *
```

7) Статические файлы (если админ без стилей)

```bash
# собрать статику внутри контейнера (если не собрана автоматически)
docker compose exec backend python manage.py collectstatic --noinput
# при необходимости пересоберите образ:
docker compose build backend
docker compose up -d backend
```

8) Логи для отладки

```bash
docker compose logs -f backend
docker compose logs -f celery
```

9) Экспорт/дамп базы

```bash
docker compose exec db pg_dump -U rpguser rpgdb > db-dump.sql
```

Если хотите, могу сгенерировать пример Postman коллекции (JSON) или добавить конкретные curl-примеры для каждого endpoint.

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
