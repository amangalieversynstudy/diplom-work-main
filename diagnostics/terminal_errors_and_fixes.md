# Terminal errors and fixes — проект "diplom-work"

Дата: 25 октября 2025

Цель: собрать реальные ошибки/сообщения из терминала/CI, которые возникали во время разработки и CI, и привязать к ним конкретные исправления (файл/коммит/короткое описание).

---

## 1) "Django settings are not configured" / Traceback при запуске pytest

Признак (как выводилось в терминале):
- Traceback (most recent call last):
  File ".../site-packages/pytest/...", line N, in <module>
    ...
  django.core.exceptions.ImproperlyConfigured: Settings are not configured.

Где найдено (артефакты/логи):
- В локальных попытках запустить `pytest` (до добавления test settings).

Причина:
- Тестовый прогон запускался без указания DJANGO_SETTINGS_MODULE, или без специального тестового settings, из-за чего Django не мог найти настройки.

Исправление (файл/коммит):
- Добавлен файл `backend/core/settings/test.py`, который использует SQLite in-memory и быстрые настройки для тестов.
- В CI/локали тесты запускаются с `DJANGO_SETTINGS_MODULE=core.settings.test` или тестовый конфиг автоматически подхватывается.

Результат:
- `pytest` успешно выполняется; сохранён `backend/junit.xml` (5 tests, 0 failures) и `backend/coverage.xml`.

---

## 2) Black formatting check failures: "would reformat X files" (CI `black --check`)

Признак (как выводилось в CI):
- "would reformat backend/core/health.py"
- "2 files would be reformatted, 0 files would be left unchanged." (black --check exit non-zero)

Где найдено (артефакты/логи):
- GitLab CI job `lint` (black --check)

Причина:
- Новые/изменённые файлы не были отформатированы Black перед пушем.

Исправление (файл/коммит):
- Запущен `black` локально (в `.venv`) и отформатированы проблемные файлы. Коммит (фикс форматирования) был запушен (commit c621b7c в сессии).

Результат:
- После коммита `black --check` проходит; CI больше не падает на этой проверке.

---

## 3) Postgres not ready / migrations fail when starting docker-compose

Признак (лог контейнера backend):
- django.db.utils.OperationalError: could not connect to server: Connection refused
  Is the server running on host "postgres" (::1) and accepting
  TCP/IP connections on port 5432?

Причина:
- Backend запускался раньше, чем Postgres готов принять соединения. Также возможна проблема с уже инициализированным томом Postgres, где нужный пользователь/роль отсутствовала вследствие предыдущей инициализации.

Исправление (файл/коммит):
- Добавлен `backend/scripts/wait_for_postgres.py` — скрипт, ожидающий доступность БД.
- В `docker-compose.yml` добавлен healthcheck для Postgres и backend команду изменили, чтобы перед миграциями запускался wait-скрипт.
- При локальной отладке рекомендовано удалять volume postgres-data при необходимости (если init-скрипт не выполнил создание роли).

Результат:
- Миграции применяются успешно; backend стартует и возвращает `200` на `/healthz`.

---

## 4) CI pipeline errors: YAML parse / incorrect artifact paths

Признак (CI job logs):
- YAML parsing error: IndentationError or mapping values are not allowed here
- Later: pytest generated coverage.xml in unexpected location so upload step could not find it ("coverage.xml not found")

Причина:
- here-doc / многострочные inline-скрипты чувствительны к отступам в `.gitlab-ci.yml`.
- pytest запускался из директории `backend`, но относительные пути для артефактов были заданы некорректно.

Исправление (файл/коммит):
- Исправлена структура `.gitlab-ci.yml`, убраны/вынесены опасные here-doc секции; path'ы для pytest-артефактов поправлены.
- Теперь pytest пишет `../backend/coverage.xml` (корректный относительный путь), job upload проверяет наличие файла и логирует диагностическую информацию.

Результат:
- CI перестал падать на YAML parse; артефакты coverage/junit доступны для последующих job'ов.

---

## 5) Husky fails in frontend CI (prepare hook error)

Признак (CI frontend job):
- Error: Husky requires a git repository to install hooks
- or: cannot find .git directory

Причина:
- В контейнере CI `npm ci` выполняется в окружении без `.git` (runner клонирует копию без метаданных или использует shallow clone), и `husky install` в script prepare пытается получить доступ к `.git`.

Исправление (файл/коммит):
- Для job'а `frontend-ci` в `.gitlab-ci.yml` установлена переменная окружения `HUSKY=0`, или временно отключён `prepare`/husky в CI.

Результат:
- `npm ci`/`npm run build` выполняются в CI без ошибок, фронтенд job проходит.

---

## 6) Codecov / coverage upload missing token or missing file

Признак (upload-job logs):
- "coverage.xml not found" или upload tool reports authentication error (missing token)

Причина:
- Либо coverage.xml генерировался не там, где ожидал uploader; либо репозиторий приватный и `CODECOV_TOKEN` не настроен в CI.

Исправление (файл/коммит):
- Исправили пути для покрытия (см. пункт 4).
- Добавили diagnostic logging в upload job и инструкцию по добавлению `CODECOV_TOKEN` в CI переменные для приватных репо.

Результат:
- coverage.xml генерируется локально (артефакт `backend/coverage.xml`), upload-job теперь может выполнить загрузку при наличии токена.

---

## 7) Прочие шумовые строки из библиотек и staticfiles

Признак:
- Много строк с "except ..." и "Traceback" в `.venv` и `staticfiles` (JS) появились в результатах поиска.

Причина:
- grep нашёл строки внутри исходников установленных библиотек и собранных статических файлов (они содержат обработчики исключений и сообщений), но это не ошибки проекта сами по себе.

Действие/рекомендация:
- Эти строки оставлены как справочная информация. Они не требовали правок проекта. Если нужно — могу собрать отдельный список проблем в static JS и передать фронтенд-специалисту.

---

## Ссылки на правки/файлы

- `backend/core/settings/test.py` — тестовые настройки (фикс для pytest)
- `backend/scripts/wait_for_postgres.py` — wait-скрипт
- `docker-compose.yml` — healthchecks и команда backend
- `.gitlab-ci.yml` — CI исправления (paths, HUSKY=0, diagnostics)
- `project_full_problems_and_fixes_report.txt` — детальная хронология и пояснения
