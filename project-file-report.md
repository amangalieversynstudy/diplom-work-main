# Project file report

Этот документ описывает файлы репозитория и их назначение. Для каждого файла даётся краткое объяснение и, если есть релевантный код, — краткий разбор ключевых частей.

Формат: для каждой секции (корень, backend/core, backend/*) перечислены файлы с описанием и пояснениями.

---

## Корневые файлы

- `Dockerfile` — образ для проекта. Содержит инструкции для установки зависимостей (apt-get libpq-dev), копирования `requirements.txt` и установки Python зависимостей, копирования кода и запуск `gunicorn core.wsgi:application`.

- `requirements.txt` — список pip-зависимостей для Django проекта используемый в CI и при сборке Docker образа. Обычно включает Django, djangorestframework, psycopg2-binary, celery, redis, pytest и другие dev-зависимости.

- `manage.py` — стандартная точка входа для Django management команд (migrate, createsuperuser, runserver). В этом файле обычно вызывается `django.core.management.execute_from_command_line`.

- `scripts/wait_for_postgres.py` — скрипт, используемый в CI и в `docker-compose` для ожидания доступности Postgres. Он пытается подключиться по заданному host/port и возвращает код 0 после успеха.

- `core/` — основной Django проект (settings, URLs, WSGI, Celery app):
  - `settings/base.py` — базовые настройки Django (INSTALLED_APPS, MIDDLEWARE, DATABASES defaults, REST_FRAMEWORK, CELERY config placeholder). Этот файл объединяет общие настройки для local/production/test.
  - `settings/local.py` — локальные настройки (например DEBUG=True, локальные секреты).
  - `settings/production.py` — production-настройки (gunicorn, staticfiles, секреты через env vars).
  - `settings/test.py` — настройки для тестов (ранее добавлены): использует SQLite in-memory (`NAME: ':memory:'`), ускоритель хеширования паролей `MD5PasswordHasher` и отключает подробное логирование. Это нужно чтобы pytest мог запускаться локально/CI без поднятого Postgres.
  - `celery.py` — инициализация Celery приложений: `Celery('core')`, загрузка конфигурации из `DJANGO_SETTINGS_MODULE` и автоматическое обнаружение задач в установленных приложениях.
  - `wsgi.py` — WSGI приложение для gunicorn: импорт и установка `DJANGO_SETTINGS_MODULE`.
  - `urls.py` — главные маршруты проекта: подключает `admin/` и `api/` префиксы для приложений `users` и `game`, а также добавлен `healthz` endpoint.
  - `health.py` — небольшой endpoint `healthz` который возвращает `JsonResponse({"status":"ok"})` — используется для docker healthcheck и CI-smoke tests.

- `tests/` — pytest тесты:
  - `test_auth.py`, `test_models.py`, `test_signals.py` — тесты для проверки регистрации/логина, поведений моделей и Django signals. Тесты настроены на pytest-django.

---

## Backend (Django)

Файлы и назначение в папке `backend`.

- `backend/Dockerfile` — образ для бэкенда. Содержит инструкции для установки зависимостей (apt-get libpq-dev), копирования `requirements.txt` и установки Python зависимостей, копирования кода и запуск `gunicorn core.wsgi:application`.

- `backend/requirements.txt` — список pip-зависимостей для Django проекта используемый в CI и при сборке Docker образа. Обычно включает Django, djangorestframework, psycopg2-binary, celery, redis, pytest и другие dev-зависимости.

- `backend/manage.py` — стандартная точка входа для Django management команд (migrate, createsuperuser, runserver). В этом файле обычно вызывается `django.core.management.execute_from_command_line`.

- `backend/scripts/wait_for_postgres.py` — скрипт, используемый в CI и в `docker-compose` для ожидания доступности Postgres. Он пытается подключиться по заданному host/port и возвращает код 0 после успеха.

- `backend/core/` — основной Django проект (settings, URLs, WSGI, Celery app):
  - `core/settings/base.py` — базовые настройки Django (INSTALLED_APPS, MIDDLEWARE, DATABASES defaults, REST_FRAMEWORK, CELERY config placeholder). Этот файл объединяет общие настройки для local/production/test.
  - `core/settings/local.py` — локальные настройки (например DEBUG=True, локальные секреты).
  - `core/settings/production.py` — production-настройки (gunicorn, staticfiles, секреты через env vars).
  - `core/settings/test.py` — настройки для тестов (ранее добавлены): использует SQLite in-memory (`NAME: ':memory:'`), ускоритель хеширования паролей `MD5PasswordHasher` и отключает подробное логирование. Это нужно чтобы pytest мог запускаться локально/CI без поднятого Postgres.
  - `core/celery.py` — инициализация Celery приложений: `Celery('core')`, загрузка конфигурации из `DJANGO_SETTINGS_MODULE` и автоматическое обнаружение задач в установленных приложениях.
  - `core/wsgi.py` — WSGI приложение для gunicorn: импорт и установка `DJANGO_SETTINGS_MODULE`.
  - `core/urls.py` — главные маршруты проекта: подключает `admin/` и `api/` префиксы для приложений `users` и `game`, а также добавлен `healthz` endpoint.
  - `core/health.py` — небольшой endpoint `healthz` который возвращает `JsonResponse({"status":"ok"})` — используется для docker healthcheck и CI-smoke tests.

- `backend/tests/` — pytest тесты:
  - `test_auth.py`, `test_models.py`, `test_signals.py` — тесты для проверки регистрации/логина, поведений моделей и Django signals. Тесты настроены на pytest-django.

## Backend apps: `users` и `game`

### users
Папка `backend/users` содержит логику аутентификации, модели пользователя и профиль.

- `models.py` — содержит кастомную модель пользователя (CustomUser) и `Profile` модель с полями `xp`, `level`, `bio`. Возможно, используется `AUTH_USER_MODEL = 'users.User'`.

- `admin.py` — регистрация модели User/Profile в Django Admin.

- `serializers.py`, `serializers_auth.py`, `serializers_password.py` — DRF сериализаторы для работы с User и Profile объектов:
  - `serializers_auth.py` содержит сериализаторы для регистрации и получения токенов (JWT), login/logout. Может использовать `djangorestframework-simplejwt` или собственную логику.
  - `serializers_password.py` содержит сериализаторы для смены/сброса пароля.

- `views.py`, `views_auth.py`, `views_password.py` — DRF представления (ViewSets или APIView) для аутентификации, управления профилем и операциями над паролем.

- `urls.py`, `urls_auth.py`, `urls_password.py` — маршруты, которые подключаются в `core/urls.py` под префиксом `api/`.

- `migrations/0001_initial.py` — автогенерированная миграция для начальных таблиц пользователей/profiles.

### game
Папка `backend/game` содержит доменную логику RPG:

- `models.py` — модели для игровых сущностей (например, `Quest`, `Achievement`, `Item` или другие), связанные с `users.Profile` через FK.

- `serializers.py` — DRF сериализаторы для модели игры.

- `views.py` — API представления (List/Create/Detail) для игровых ресурсов.

- `urls.py` — маршруты для игровых API.

- `admin.py` — регистрация игровых моделей в Django Admin.

- `migrations/` — миграции для игровых моделей.


## Скрипты и утилиты

- `backend/scripts/wait_for_postgres.py` — небольшой скрипт на Python, который пытается подключиться к Postgres (psycopg2) в цикле с таймаутом, используется для ожидания готовности БД в CI и docker-compose.


## Файлы конфигурации и CI

- `.gitlab-ci.yml` — основной pipeline для GitLab: stages lint/test/frontend/docs-lint. В `lint` стадии запускает `black --check` и `flake8`. В `test` стадии поднимает сервисы Postgres/Redis, устанавливает зависимости, ждёт БД и запускает pytest; артефакты `backend/coverage.xml` и `backend/pytest-results.xml` сохраняются. Есть job `frontend-ci` на Node для lint+build фронтенда. Job `flake8-docstrings-baseline` собирает докстринговую статистику.

- `.github/workflows/ci.yml` — альтернативная CI конфигурация для GitHub Actions (если присутствует) — содержит похожие шаги.

- `.pre-commit-config.yaml` — конфигурация pre-commit hooks (black, isort, flake8 и др.) — используется локально.

- `.flake8` — flake8 конфигурация (макс длина строки 88, исключения для миграций и .next кэша фронтенда).
