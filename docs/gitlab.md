# GitLab CI/CD Handbook

> Обновлено: 18 ноября 2025 г.

## 1. Обзор пайплайна

Пайплайн состоит из шести стадий и запускается для всех коммитов в ветках и MR:

| Stage   | Jobs                                                                                 | Назначение |
|---------|--------------------------------------------------------------------------------------|------------|
| `lint`  | `frontend-lint`                                                                      | Быстрая проверка ESLint для Next.js |
| `test`  | `backend-test`                                                                       | Pytest + coverage, использует кэш pip внутри job |
| `frontend` | `frontend-build`                                                                  | Prod-сборка Next.js (артефакты `.next`) |
| `build` | `backend-build-image`                                                                | Docker build образа бэкенда (BuildKit + docker-in-docker) |
| `smoke` | `smoke-backend-image`                                                                | Мини smoke: загрузка образа, `docker run`, проверка `/healthz` |
| `deploy` | `deploy-local` (manual)                                                             | Поднимает Redis/Postgres/Backend/Celery внутри CI и прогоняет миграции + демо-данные |

- Все джобы работают на shared SaaS runner-ах, поэтому теги не используются.
- Stages `build`, `smoke`, `deploy` зависят от Docker; там используется сервис `docker:dind`. GitLab.com shared runner-ы не разрешают флаг `privileged`, поэтому полагаемся на стандартные настройки runner-а и подключаемся к демону по `tcp://docker:2375`.

## 2. Глобальные переменные и кэш

| Переменная | Где зашита | Значение по умолчанию | Назначение |
|------------|------------|-----------------------|------------|
| `DOCKER_HOST` | docker job-ы | `tcp://docker:2375` | Соединение с сервисом docker:dind |
| `DOCKER_TLS_CERTDIR` | docker job-ы | пустая строка | Выключает TLS, упрощает подключение с shared runner |
| `DOCKER_DRIVER` | docker job-ы | `overlay2` | Рекомендуемый storage driver для SaaS runner |
| `DEMO_SEED` / `ALLOW_DEMO_SEED` | `deploy-local` | `true` | Управляют засевом демо-контента |

Кэшируется только `frontend/node_modules`. Папку `.next` мы не кэшируем (прогрев 15–20 с).

## 3. Диагностика частых сбоев

| Симптом | Что делать |
|---------|------------|
| `error during connect: ... lookup docker ...` | Значит не поднят `docker:dind`. Проверь, что job наследует блок `services` и `privileged: true`.
| `Cannot connect to the Docker daemon` | Убедись, что переменные `DOCKER_HOST` и `DOCKER_TLS_CERTDIR` заданы; при необходимости очисти кэш проекта и перезапусти job.
| `frontend-lint` падает с `npm ci` | Проблемы в lock-файле. Удали `frontend/node_modules` локально, пересобери `npm install`, закомить `package-lock.json` и перезапусти.
| `backend-test` падает из‑за psycopg | Не поднят Postgres (pytest использует SQLite in-memory, поэтому ошибки означают сломанные миграции/фикстуры).
| `deploy-local` зависает на `healthz` | Посмотри `CI/CD → Jobs → deploy-local → Trace`. Если контейнер упал, изучи `docker logs ci_local_backend` (автоматически печатается перед завершением job).

## 4. Как запускать мануальные шаги

1. Открой вкладку **CI/CD → Pipelines**.
2. Найди нужный pipeline → открой.
3. В стадии `deploy` нажми кнопку `play` рядом с `deploy-local`.
4. После запуска job можно смотреть здоровье `http://localhost:8000/healthz` прямо из логов (используем `curl`).

> После завершения job контейнеры и сеть удаляются автоматически; если нужно оставить их для отладки, закомментируй последние строки в `.gitlab-ci.yml` и запусти pipeline в тестовой ветке.

## 5. Чек-лист перед merge

- ✅ `frontend-lint` и `frontend-build` зелёные (если не трогали фронт — job-ы пропускаются `rules:changes`).
- ✅ `backend-test` зелёный и выгружает pytest-репорты.
- ✅ `backend-build-image` → `smoke-backend-image` проходят без ошибок docker.
- ✅ Важные merge request-и сопровождаются ссылкой на актуальные инструкции (README, docs/roadmap, этот файл).

Хочешь расширить пайплайн (SAST, dependency scanning, staging deploy)? Добавь отдельную MR и ссылку на этот документ, чтобы сохранять единое место правды.
