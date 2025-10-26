# Руководство по деплою: локально и staging

Этот документ описывает, как запускать локальную демонстрационную среду (deploy-local) и как выкатывать на staging (deploy-staging) через GitLab CI, а также флаги для автозагрузки демо-данных.

## Содержание

- [Быстрый старт](#быстрый-старт)
- [Локальная демонстрация (deploy-local)](#1-локальная-демонстрация-deploy-local)
- [Staging с демо-данными](#2-staging-с-демо-данными)
- [Обзор пайплайна](#обзор-пайплайна)
- [DEMO флаги и защита](#demo-флаги-и-защита)
- [Локальный деплой (deploy-local)](#локальный-деплой-deploy-local)
- [Staging деплой (deploy-staging)](#staging-деплой-deploy-staging)
- [Demo management-команды](#demo-management-команды)
- [Ручное тестирование API (Postman)](#ручное-тестирование-api-postman)
- [Частые проблемы](#частые-проблемы)
- [Безопасность](#безопасность)

## Быстрый старт

<a id="quickstart"></a>

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

## Быстрый старт

<a id="quickstart"></a>

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
