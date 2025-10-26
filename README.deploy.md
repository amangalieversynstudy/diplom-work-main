# Руководство по деплою: локально и staging

Этот документ описывает, как запускать локальную демонстрационную среду (deploy-local) и как выкатывать на staging (deploy-staging) через GitLab CI, а также флаги для автозагрузки демо-данных.

## Содержание

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
Содержание

- [Быстрый старт](#%D0%91%D1%8B%D1%81%D1%82%D1%80%D1%8B%D0%B9-%D1%81%D1%82%D0%B0%D1%80%D1%82)
  - [1) Локальная демонстрация (deploy-local)](#1-%D0%9B%D0%BE%D0%BA%D0%B0%D0%BB%D1%8C%D0%BD%D0%B0%D1%8F-%D0%B4%D0%B5%D0%BC%D0%BE%D0%BD%D1%81%D1%82%D1%80%D0%B0%D1%86%D0%B8%D1%8F-deploy-local)
  - [2) Staging с демо-данными](#2-staging-%D1%81-%D0%B4%D0%B5%D0%BC%D0%BE-%D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D0%BC%D0%B8)
- [Обзор пайплайна](#%D0%9E%D0%B1%D0%B7%D0%BE%D1%80-%D0%BF%D0%B0%D0%B9%D0%BF%D0%BB%D0%B0%D0%B9%D0%BD%D0%B0)
- [DEMO флаги и защита](#demo-%D1%84%D0%BB%D0%B0%D0%B3%D0%B8-%D0%B8-%D0%B7%D0%B0%D1%89%D0%B8%D1%82%D0%B0)
- [Локальный деплой (deploy-local)](#%D0%9B%D0%BE%D0%BA%D0%B0%D0%BB%D1%8C%D0%BD%D1%8B%D0%B9-%D0%B4%D0%B5%D0%BF%D0%BB%D0%BE%D0%B9-deploy-local)
- [Staging деплой (deploy-staging)](#staging-%D0%B4%D0%B5%D0%BF%D0%BB%D0%BE%D0%B9-deploy-staging)
- [Demo management-команды](#demo-management-%D0%BA%D0%BE%D0%BC%D0%B0%D0%BD%D0%B4%D1%8B)
- [Ручное тестирование API (Postman)](#%D0%A0%D1%83%D1%87%D0%BD%D0%BE%D0%B5-%D1%82%D0%B5%D1%81%D1%82%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD%D0%B8%D0%B5-api-postman)
- [Частые проблемы](#%D0%A7%D0%B0%D1%81%D1%82%D1%8B%D0%B5-%D0%BF%D1%80%D0%BE%D0%B1%D0%BB%D0%B5%D0%BC%D1%8B)
- [Безопасность](#%D0%91%D0%B5%D0%B7%D0%BE%D0%BF%D0%B0%D1%81%D0%BD%D0%BE%D1%81%D1%82%D1%8C)
- [Make команды и .env](#make-%D0%BA%D0%BE%D0%BC%D0%B0%D0%BD%D0%B4%D1%8B-%D0%B8-env)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Быстрый старт

<a id="quickstart"></a>

> Примечание: как только вы завершили знакомство и переходите к работе с кодом проекта, используйте раздел [Make команды и .env](#make-команды-и-env) — это самый быстрый путь для локального запуска и повседневных операций.

### 1) Локальная демонстрация (deploy-local)

<a id="quickstart-local"></a>
1. Убедитесь, что локальный GitLab Runner с тегом `local` монтирует Docker socket (`/var/run/docker.sock:/var/run/docker.sock`).
2. В GitLab → CI/CD → Pipelines запустите вручную job `deploy-local`.
3. Дождитесь сообщения:
  - `Backend started locally on http://localhost:8000`
  - `Admin login: admin/admin123`
4. Откройте `http://localhost:8000/healthz` — должно вернуть `{ "status": "ok" }`.
5. Для ручного API-теста импортируйте в Postman:
  - Коллекцию: `diagnostics/postman/RPG.postman_collection.json`
  - Окружение: `diagnostics/postman/Local.postman_environment.json`

### 2) Staging с демо-данными

<a id="quickstart-staging"></a>
1. В GitLab → Settings → CI/CD → Variables добавьте:
  - `DEPLOY_HOST` (адрес сервера)
  - `DEPLOY_USER` (SSH пользователь)
  - `SSH_PRIVATE_KEY` (masked, protected)
  - Опционально: `DEPLOY_DIR` (папка с docker-compose.yml)
2. Чтобы засеять демо, добавьте/включите:
  - `DEMO_SEED = true`
  - `ALLOW_DEMO_SEED = true`
3. Запустите вручную `deploy-staging`.
4. В логе увидите "Seeding demo data on staging..." и сводку `print_demo_summary`.
5. Отключите флаги DEMO_SEED/ALLOW_DEMO_SEED после демонстрации.

## Обзор пайплайна

Стейджи: `lint` → `test` → `frontend` → `docs-lint` → `build` → `deploy`.

Ключевые job’ы:
- `build-backend-image` — собирает Docker-образ бэкенда и сохраняет артефакт `backend_image.tar`.
- `smoke-test-image` — опционально проверяет образ простым health-check.
- `deploy-local` — ручной запуск, поднимает локальный стек (Postgres, Redis, Backend, Celery) на вашей машине через Docker сокет.
- `deploy-staging` — ручной SSH деплой на staging-хост с использованием docker-compose (миграции + опциональный сидинг демо-данных).

## DEMO флаги и защита

В проекте предусмотрен безопасный механизм автозагрузки демо-данных.

- `DEMO_SEED` — флаг на уровне job’а (CI переменная), включает запуск сидинга.
- `ALLOW_DEMO_SEED` — переменная окружения приложения, разрешающая сидинг в средах с `DEBUG = False` (staging/prod). Без неё сидинг в non-debug среде игнорируется.

Гарантия безопасности:
- Команды `load_demo_content` и `create_demo_superuser` в non-debug режимах (DEBUG=False) выполняются только если `ALLOW_DEMO_SEED=true` в окружении контейнера.
- По умолчанию:
  - В `deploy-local`: `DEMO_SEED=true`, `ALLOW_DEMO_SEED=true` (безопасно для локали).
  - В `deploy-staging`: `DEMO_SEED=false`, `ALLOW_DEMO_SEED=false` (демо не засыпается).

## Локальный деплой (deploy-local)

Требования к локальному GitLab Runner:
- Executor: docker (privileged не обязателен).
- Должен быть проброшен Docker socket хоста: `/var/run/docker.sock:/var/run/docker.sock`.
- Раннер должен иметь тег `local` (job помечен `tags: [local]`).

Что делает job:
1. Проверяет доступ к Docker сокету.
2. Создаёт сеть `ci_local_net`.
3. Поднимает `redis:7` и `postgres:15` (контейнеры `ci_local_redis`, `ci_local_postgres`).
4. Загружает `backend_image.tar` и запускает:
   - `python manage.py migrate --noinput`
   - `python manage.py collectstatic --noinput`
5. Если `DEMO_SEED=true`:
   - `python manage.py load_demo_content`
   - `python manage.py create_demo_superuser`
   - `python manage.py print_demo_summary`
6. Стартует backend (`ci_local_backend`) и celery (`ci_local_celery`).
7. Ждёт health на `http://localhost:8000/healthz` и печатает:
   - URL: `http://localhost:8000`
   - Admin: `${DEMO_ADMIN_USERNAME}/${DEMO_ADMIN_PASSWORD}` (по умолчанию `admin/admin123`).

Переменные по умолчанию (можно переопределить в CI Variables):
- `POSTGRES_DB=rpgdb`, `POSTGRES_USER=rpguser`, `POSTGRES_PASSWORD=rpgpass`
- `DEMO_ADMIN_USERNAME=admin`, `DEMO_ADMIN_EMAIL=admin@example.com`, `DEMO_ADMIN_PASSWORD=admin123`
- `DEMO_SEED=true`, `ALLOW_DEMO_SEED=true`

## Staging деплой (deploy-staging)

Требования:
- На staging-хосте должен быть установлен `docker-compose` и настроен проект в каталоге `$DEPLOY_DIR`.
- CI Variables:
  - `DEPLOY_HOST` — адрес хоста.
  - `DEPLOY_USER` — SSH пользователь.
  - `SSH_PRIVATE_KEY` — приватный ключ (CI masked/Protected).
  - (опционально) `DEPLOY_DIR` — каталог с docker-compose.yml.
  - (опционально) `DOCKER_REGISTRY`, `DOCKER_USERNAME`, `DOCKER_PASSWORD` — для pull образа по sha.

Что делает job:
1. Подключается по SSH, выполняет `docker-compose pull || true` и `docker-compose up -d`.
2. Запускает миграции: `docker-compose exec backend python manage.py migrate --noinput`.
3. Если `DEMO_SEED=true`, дополнительно выполняет сидинг:
   - Передаёт в `docker-compose exec` переменную `ALLOW_DEMO_SEED` (по умолчанию `false`).
   - `load_demo_content`, `create_demo_superuser`, `print_demo_summary` выполнятся только если `ALLOW_DEMO_SEED=true`.

Рекомендации по staging:
- Держите `DEMO_SEED=false` и `ALLOW_DEMO_SEED=false` по умолчанию.
- Включайте оба флага только для временных/превью окружений.

## Demo management-команды

- `python manage.py load_demo_content`
  - Создаёт локации и миссии (Intro, Gate с prerequisite Intro, Repeatable).
  - В non-debug средах требует `ALLOW_DEMO_SEED=true`.
- `python manage.py create_demo_superuser`
  - Создаёт суперпользователя из переменных окружения:
    - `DEMO_ADMIN_USERNAME`, `DEMO_ADMIN_EMAIL`, `DEMO_ADMIN_PASSWORD`
  - В non-debug средах требует `ALLOW_DEMO_SEED=true`.
- `python manage.py print_demo_summary`
  - Печатает краткую сводку по локациям/миссиям.

## Ручное тестирование API (Postman)

Импортируйте:
- Коллекция: `diagnostics/postman/RPG.postman_collection.json`
- Окружение: `diagnostics/postman/Local.postman_environment.json`

Последовательность: Register → Login (автосохранит access/refresh) → Me → Missions → Start/Complete → Progress → Logout.

## Частые проблемы

- `ERROR: /var/run/docker.sock is not available inside the job container`
  - Убедитесь, что локальный runner монтирует сокет Docker: `volumes = ["/var/run/docker.sock:/var/run/docker.sock"]` в `config.toml`.
- `415 Unsupported Media Type` при POST запросах
  - Встроено решение: DRF парсеры включают JSON/Form/MultiPart.
- Предупреждение Swagger рендереров
  - Отключено: `SWAGGER_USE_COMPAT_RENDERERS = False`.

## Безопасность

- Никогда не включайте `DEMO_SEED`/`ALLOW_DEMO_SEED` на проде без осознанной необходимости.
- Даже при запуске команд вручную в non-debug средах они не внесут изменения без `ALLOW_DEMO_SEED=true`.

---
Если потребуется, можно расширить deploy-staging автоматическим выводом публичного URL/cred'ов и интегрировать шаги очистки демо-данных.

## Make команды и .env

Для удобства доступны цели Make (см. `Makefile`). Рекомендуется создать локальный файл `.env` на основе примера ниже — переменные будут автоматически подхвачены Makefile.

Пример `.env` (скопируйте `.env.example` → `.env`):

```
POSTGRES_DB=rpgdb
POSTGRES_USER=rpguser
POSTGRES_PASSWORD=rpgpass
POSTGRES_HOST=ci_local_postgres
REDIS_URL=redis://ci_local_redis:6379/0

# staging
DEPLOY_HOST=
DEPLOY_USER=
DEPLOY_DIR=/srv/diplom-work
DEMO_SEED=false
ALLOW_DEMO_SEED=false
```

Команды:

- `make deploy-local` — локальный стек: сеть/Redis/Postgres → build backend-local → migrate/collectstatic → seed-demo → run backend+celery → health.
- `make seed-demo` — загрузить демо-данные, создать демо-админа, вывести сводку.
- `make stop-local` — остановить/удалить локальные контейнеры.
- `make logs` — логи бэкенда.
- `make redeploy-local` — stop + deploy-local.
- `make clean` — удалить локальные артефакты (контейнеры, сеть, образ backend-local).
- `make ps` — показать контейнеры ci_local_*.
- `make curl-health` — быстрый проверочный запрос к /healthz.
- `make deploy-staging` — деплой на staging по SSH (docker-compose). Требуются `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_DIR`. Для демо включайте `DEMO_SEED=true` и при необходимости `ALLOW_DEMO_SEED=true`.
