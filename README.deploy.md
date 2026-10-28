# Деплой — RPG Academy (Railway + Vercel)

Боевой стенд:

| Часть | Где | Как собирается |
|---|---|---|
| **Backend** (Django/DRF + WebSocket) | **Railway** | Docker из `Dockerfile.backend` (указан в `railway.toml`) |
| **PostgreSQL** | **Railway** (плагин) | даёт `DATABASE_URL` |
| **Frontend** (Next.js) | **Vercel** (бесплатно) | `next build`, root = `frontend/` |

Тариф Railway **Hobby (~$5/мес)**: два сервиса — бэкенд и Postgres. Redis не нужен: бэкенд работает **одним процессом Daphne** (HTTP и WebSocket), счётчики лимитов живут в его памяти. Redis понадобится, только если запустить несколько процессов или реплик (тогда задай `REDIS_URL`).

```
Браузер ── HTTPS ──► Vercel (Next.js)
   │                      │  REST /api  +  WebSocket /ws/runner
   └──────────────────────┴────────────► Railway: Django (один процесс Daphne) ─► Postgres
                                                         └─► Resend (письма), Judge0 (песочница)
```

Содержание: [Backend → Railway](#backend-railway) · [Frontend → Vercel](#frontend-vercel) · [Локально](#quickstart-local) · [Проверка](#проверка-после-деплоя) · [Частые проблемы](#частые-проблемы)

---

## <a id="backend-railway"></a>1. Backend → Railway

### 1.1. Сервис
1. Railway → **New Project → Deploy from GitHub repo** → выбери репозиторий.
2. Branch — рабочая ветка деплоя (**`feature/final-polish`**).
3. Railway прочитает `railway.toml`: сборка по `Dockerfile.backend`, проверка здоровья `/healthz`. Менять builder не нужно.
4. **Settings → Deploy → Custom Start Command оставь пустым.** Поле в панели важнее файла и перебьёт команду образа.
5. **Settings → Networking → Generate Domain** — публичный адрес `<сервис>.up.railway.app`.

Команда запуска зашита в образ (`CMD` в `Dockerfile.backend`):
```
python manage.py release  →  exec daphne (один процесс, HTTP + WebSocket)
```
`release` за один запуск Python делает: `migrate` → `ensure_superuser` → `seed_course` → `sync_course_protection`. Статика собирается при сборке образа. `seed_course` загружает ranks, class_roles и оба курса (вводный и «Путь Мастера») **только если их ещё нет** — правки курса в админке и Studio при перезапуске не затираются. Чтобы выкатить новую версию встроенных курсов из фикстур (это перезапишет правки в них; владельцы курсов сохраняются), один раз выполни в Railway → backend → **Run a command**: `python manage.py seed_course --force`. `sync_course_protection` доводит уже работающую базу до текущих фикстур: личные варианты заданий, списки «ещё не проходили» и вопросы «объясни». Если любой шаг упал, сервер не стартует и деплой считается неудачным (ошибка не скрывается).

После выкладки один раз проверьте на сервере, что код реально запускается: `python manage.py check_runner` (три пробных запуска через ту же цепочку, что и кнопка «Запустить»; публичный ce.judge0.com бывает занят, команда это покажет).

**Преподаватели пилота** регистрируются сами: выбирают «Я преподаватель» и вводят **код преподавателя**, или ученик позже вводит его в профиле («Активировать доступ преподавателя»). Код — переменная `TEACHER_INVITE_CODE`; если её нет, действует код пилота `PILOT-2026`. Он есть в публичном репозитории, поэтому **задай свой** перед пилотом (`off` — выключить код). Код даёт роль преподавателя своих курсов: свои закрытые курсы и классы, только их ученики, без доступа в админку. «Проверенного» методиста (публичные курсы, все их ученики) по-прежнему делает суперпользователь в `/admin/`.

Встроенные курсы закрепляются за методистом командой (Railway → backend → **Run a command**): `python manage.py set_course_owner python-intro <логин>` и то же для `python-continued`. Обычный преподаватель видит своих учеников, когда создаст курс в Студии (или развернёт демо-пример) и даст группе код класса.

### 1.2. База
- **Add → Database → PostgreSQL**.
- В сервисе backend: Variables → `DATABASE_URL` = `${{ Postgres.DATABASE_URL }}` (ссылка на плагин).
- Redis не добавляй: без `REDIS_URL` кэш живёт в памяти процесса. Это экономит отдельный платный сервис.

### 1.3. Переменные окружения (Variables)
| Переменная | Значение | Зачем |
|---|---|---|
| `DJANGO_SECRET_KEY` | `${{ secret(64) }}` | **обязательно** — прод не стартует с дефолтом |
| `DATABASE_URL` | `${{ Postgres.DATABASE_URL }}` | БД |
| `ALLOWED_HOSTS` | `<сервис>.up.railway.app` | **обязательно** — без неё прод не стартует (`*` запрещён). Домен `RAILWAY_PUBLIC_DOMAIN`, хост проверки здоровья Railway и хост фронтенда (из `FRONTEND_URL`, нужен для WebSocket) добавляются сами |
| `CSRF_TRUSTED_ORIGINS` | `https://<сервис>.up.railway.app` | вход в `/admin/` по HTTPS; умолчаний нет |
| `FRONTEND_URL` | `https://<проект>.vercel.app` | ссылки в письмах, CORS и проверка WebSocket |
| `TEACHER_INVITE_CODE` | свой код, напр. `KAFEDRA-2026-<что-то своё>` | код преподавателя (без переменной — публичный `PILOT-2026`) |
| `DJANGO_SUPERUSER_USERNAME` / `_EMAIL` / `_PASSWORD` | твои данные | суперпользователь создаётся при старте, если его нет. **После первого входа удали `_PASSWORD`** |
| `GEMINI_API_KEY` | ключ Google AI Studio | ИИ-наставник (пусто — выключен) |
| `SECURE_SSL_REDIRECT` | `True` (по умолчанию) | редирект http→https; `/healthz` исключён. Отключай только для отладки |
| `RESEND_API_KEY` | ключ Resend | реальная отправка писем (Railway блокирует SMTP) |
| `DEFAULT_FROM_EMAIL` | `noreply@твойдомен` | отправитель писем |
| `ENABLE_STREAK_SCHEDULER` | `1` | ежедневное письмо-напоминание о серии |
| `STREAK_REMINDER_HOUR` / `_MINUTE` | напр. `13` / `0` (UTC) | время рассылки (13:00 UTC = 18:00 Алматы) |
| `SENTRY_DSN` | (опц.) | мониторинг ошибок |
| `RUNNER_JUDGE0_URL` / `RUNNER_JUDGE0_KEY` | (опц.) | своя песочница; по умолчанию публичный ce.judge0.com, Python 3.12 (`RUNNER_JUDGE0_LANGUAGE_ID=100`) |
| `PILOT_STARTED_AT` | (опц.) напр. `2026-11-02T00:00:00+05:00` | с какого момента отчёт пилота считает измерения преподавателей |

> `DJANGO_SETTINGS_MODULE=core.settings.production` задан в образе (`Dockerfile.backend`) — отдельно задавать не нужно. Не задавай `REDIS_URL` и `RUNNER_ALLOW_UNSAFE_FALLBACK`.

> **CORS:** прод автоматически разрешает домены вида `diplom-work-main*.vercel.app` (regex в `production.py`). Если имя Vercel-проекта другое — добавь `CORS_ALLOWED_ORIGINS=https://твой-фронт.vercel.app`. Для своего домена задай ещё `CSRF_TRUSTED_ORIGINS=https://твой-домен`.

### 1.3.1. Резервные копии Postgres
Включи бэкапы плагина (Postgres → Backups → ежедневное расписание) либо запускай ежедневный `pg_dump "$DATABASE_URL" -Fc -f backup.dump` (отдельный cron-сервис) с хранением вне Railway. До старта пилота: сделай копию вручную и проверь, что она восстанавливается (`pg_restore` в пустую базу).

### 1.4. Первый запуск
После успешного деплоя (первый старт мигрирует пустую базу, проверка здоровья ждёт до 5 минут):
- Открой `https://<backend>.up.railway.app/healthz` → `{"status":"ok"}`.
- Зайди в `/admin/` суперпользователем из `DJANGO_SUPERUSER_*` (он создаётся сам при старте), затем **удали переменную `DJANGO_SUPERUSER_PASSWORD`**.
- В Vercel обнови `NEXT_PUBLIC_API_BASE` на новый адрес бэкенда и сделай **Redeploy** (значение вшивается при сборке).
- Проверь путь преподавателя: регистрация «Я преподаватель» + код → кабинет → «Развернуть демо-пример» → «Глазами студента».

**Расход на Hobby.** Один процесс Django ≈ 150–200 МБ памяти, Postgres ≈ 100–200 МБ, процессор почти простаивает: обычно это укладывается в $5 тарифа. Смотри Usage в Railway через неделю пилота.

### 1.5. Запуск кода учеников
На Railway нет Docker-in-Docker, поэтому код исполняется во внешней песочнице **Judge0** (`RUNNER_JUDGE0_URL`). Если Judge0 не задан или недоступен, студент получает сообщение «песочница недоступна» и код **не выполняется** — локальный subprocess-фолбэк в production выключен, потому что он запускает чужой код на сервере приложения. Не задавай `RUNNER_ALLOW_UNSAFE_FALLBACK=True` в Railway (проверь, что такой переменной там нет). Каждый отказ Judge0 пишется в логи деплоя (`Judge0 request failed` / `Judge0 answered HTTP …`).

---

### 1.6. Аналитика обучения (цифровой след)
Сервер сам записывает, что делает ученик: каждый запуск кода (`CodeRun`: исход, тип ошибки, время, размеры — но не сам код) и события (`LearningEvent`: вход, начало и конец миссии, открытие шага, ответы на квиз, подсказки, вызовы AI). Смотреть можно в `/admin/` (только чтение). Сбой самой песочницы в попытки ученика не засчитывается.

- **Согласие.** Ученик отмечает его при регистрации или в профиле (по умолчанию выключено). В экспорт попадают только согласившиеся ученики.
- **Экспорт для анализа:** `python manage.py export_learning_data --out analytics_export` — CSV без имён, почт и кода; пользователи заменены хешем. Задай секрет `ANALYTICS_EXPORT_SALT` (иначе используется `SECRET_KEY`) и не публикуй его вместе с данными.
- **Срок хранения:** `LEARNING_DATA_RETENTION_DAYS` (по умолчанию 730). Очистка: `python manage.py prune_learning_data` (`--dry-run` — только посчитать); запускай ежедневно (см. ниже).
- **Регулярная очистка (Railway Cron).** Создай отдельный сервис из того же репозитория и образа, в Settings → Cron Schedule укажи `0 3 * * *` (раз в сутки), Start Command: `python manage.py prune_learning_data`, переменные — те же, что у backend (`DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_SETTINGS_MODULE=core.settings.production`, `ALLOWED_HOSTS`). Зачем: срок хранения данных пилота ограничен `LEARNING_DATA_RETENTION_DAYS`, без очистки обязательство перед участниками не выполняется.
- Лимит запусков кода: 5 за 10 секунд и 20 в минуту на пользователя (счётчики в кэше процесса; при нескольких процессах нужен общий Redis, `REDIS_URL`).

---

## <a id="frontend-vercel"></a>2. Frontend → Vercel

1. Vercel → **Add New → Project** → импортируй тот же репозиторий.
2. **Root Directory = `frontend`**, Framework = **Next.js** (определится сам).
3. Branch — та же `feature/final-polish`.
4. Переменная окружения:
   | Переменная | Значение |
   |---|---|
   | `NEXT_PUBLIC_API_BASE` | `https://<backend>.up.railway.app/api` |
5. Deploy. Vercel сам делает `next build`.

После деплоя фронт будет ходить в API на Railway; CORS уже настроен на стороне бэка (см. 1.3).

---

## <a id="quickstart-local"></a>3. Локальная разработка

**Вариант А — Docker-стек** (db + backend + frontend одной командой):
```bash
cp .env.example .env          # заполни при необходимости
docker compose up --build
# backend: http://localhost:8000 , frontend: http://localhost:3000
```

**Вариант Б — вручную:**
```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # рабочие пакеты + pytest
export DJANGO_SETTINGS_MODULE=core.settings.local
python manage.py release          # миграции + встроенные курсы, как на сервере
python manage.py runserver        # http://localhost:8000

# frontend (в другом терминале)
cd frontend && npm install
npm run dev                       # http://localhost:3000
```
Локально письма по умолчанию идут в консоль (`EMAIL_BACKEND=console`), запуск кода — через Docker-песочницу (если есть Docker), иначе Judge0, иначе локальный фолбэк (включён только в `core.settings.local`).

---

## Проверка после деплоя
- `GET /healthz` → `{"status":"ok"}`.
- Регистрация → письмо активации (проверь Resend dashboard) → активация → вход.
- `/worlds` → пройти миссию (story/quiz/code) → начисление XP/серии.
- `/admin/` → создание/редактирование курса.
- Тесты/CI: `.github/workflows/ci.yml` (бэкенд `pytest`, фронт `npm run build`).

## Частые проблемы
| Симптом | Причина / решение |
|---|---|
| Прод не стартует, `ImproperlyConfigured` | не задан `DJANGO_SECRET_KEY` или `ALLOWED_HOSTS` |
| Деплой висит на Healthcheck и падает | в панели задан Custom Start Command (очисти его) или упал `release` — смотри Deploy Logs |
| 500 на любом API, в логах Redis | задан `REDIS_URL` на несуществующий Redis — удали переменную |
| Код учеников не запускается с сайта, WebSocket закрывается | `FRONTEND_URL` не совпадает с адресом фронтенда (хост берётся из него) |
| Письма не приходят | нет `RESEND_API_KEY`/`DEFAULT_FROM_EMAIL`, или домен не верифицирован в Resend |
| CORS-ошибка на фронте | имя Vercel-проекта не подпадает под regex — задай `CORS_ALLOWED_ORIGINS` |
| Запуск кода «недоступен» | Judge0 не отвечает — смотри логи (`Judge0 request failed`), задай свой `RUNNER_JUDGE0_URL` (+ ключ); фолбэк в production не включай |
| Письмо о серии не уходит | `ENABLE_STREAK_SCHEDULER=1` + время в UTC; проверь логи деплоя |

---

## (Опционально) Self-host на VPS
В репозитории остаётся альтернативный путь self-hosting: `deploy.sh` + `docker-compose.prod.yml` + `nginx.conf` (nginx + Let's Encrypt). Он независим от Railway/Vercel и при них не используется.
