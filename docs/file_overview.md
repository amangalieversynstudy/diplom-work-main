# Обзор ключевых файлов и директорий

| Путь | Назначение |
| --- | --- |
| `docker-compose.yml` | Поднимает локальный стек: Postgres, Redis, Django backend, Celery и Next.js frontend. |
| `Makefile` | Содержит удобные цели (`deploy-local`, `stop-local`, `logs`) для разработчиков, которые предпочитают make. |
| `README.md` | Главный файл, описывающий запуск, тестирование и ссылки на дополнительные инструкции. |
| `README.deploy.md` | Расширенный гайд по деплою (локально, staging, production) и CI/CD переменным. |
| `backend/` | Django‑проект: код API, Celery задач, настройки, тесты. |
| `backend/core/settings/` | Базовые, локальные, продакшен и тестовые настройки Django. |
| `backend/game/` | Логика RPG-миссий: модели, сериализаторы, вьюхи и тесты. |
| `backend/game/runner.py` | Docker-песочница для Python-кода + subprocess fallback (Railway). |
| `backend/game/consumers.py` | WebSocket consumer стримингового раннера (`/ws/runner/`). |
| `backend/game/views.py` | `AIAssistView` (Gemini 2.5 Flash), `CodeRunnerView`, `IntroStatusView`, ViewSet-ы миссий/задач. |
| `backend/game/fixtures/intro_course.json` | Вводный курс: 4 миссии × 3 задачи (Story / Quiz / Code). |
| `backend/game/throttles.py` | Rate-limits для AI (10/min) и code runner (20/min + 5/10s burst). |
| `Dockerfile.backend` | Production Docker image (Railway деплой). |
| `railway.toml` | Railway конфиг: builder + startCommand (migrate → loaddata → daphne). |
| `backend/users/` | Пользовательские модели, сериализаторы и API endpoints для аутентификации/профиля. |
| `backend/scripts/wait_for_postgres.py` | Скрипт, который ждёт доступности Postgres перед запуском миграций (используется в Docker). |
| `frontend/` | Приложение на Next.js: странички, компоненты, стили и конфиги. |
| `frontend/lib/i18n.js` | Словари переводов (RU/EN) для UI.
| `frontend/components/` | Повторно используемые UI-компоненты (карточки, степперы, код-раннер и т.д.). |
| `frontend/components/CodeRunnerPanel.jsx` | Редактор + xterm.js терминал (WebSocket runner), AI Summon, инвентарь, resize. |
| `frontend/components/Terminal.jsx` | xterm.js обёртка (SSR-safe dynamic import, FitAddon). |
| `frontend/components/MissionStepper.jsx` | Левая колонка миссии — список задач с sequential unlock. |
| `frontend/lib/api.js` | Axios-клиент с JWT interceptor + все API-обёртки (Missions, AIAssist, Profile, и т.д.). |
| `frontend/pages/` | Страницы Next.js: `/worlds`, `/missions/[id]`, `/leaderboard` и т.п. |
| `frontend/Dockerfile` | Сборка фронтенд-контейнера (используется docker compose). |
| `ci/` | Дополнительные CI-скрипты, инструкции и README по GitLab. |
| `docs/` | Различные отчёты и вспомогательная документация (нагрузочные сценарии, postman коллекции и т.д.). |
| `diagnostics/` | Тестовые сценарии и отчёты (schemathesis, k6, postman коллекции). |
| `scripts/` | Вспомогательные shell-скрипты (например, проверки gitlab env vars, создание merge request). |

> Если нужна более детальная карта по конкретному модулю, дайте знать — можно расширить таблицу или добавить диаграмму.
