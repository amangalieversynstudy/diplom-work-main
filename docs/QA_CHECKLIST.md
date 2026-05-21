# QA Checklist: RPG Academy — Полное Ручное Тестирование

> **Ставь метки прямо здесь:** ✅ прошло | ❌ упало (добавь заметку) | ⚠️ частично
>
> Весь путь занимает ~45–60 минут при первом прогоне, ~20 минут при повторном.
> Критический путь для демо комиссии — раздел **12** в конце файла.

---

## 0. Подготовка окружения (делай один раз перед тестами)

### 0.1 Локальный запуск через Docker

```bash
# 1. Убедись, что Docker Desktop запущен
docker info

# 2. Поднять все сервисы (DB + Redis + Backend + Frontend)
docker compose up -d db redis backend frontend

# 3. Дождаться healthy (30–60 сек)
docker compose ps
# Все сервисы должны быть State: Up (healthy) или running

# 4. Применить миграции + загрузить вводный курс
docker compose exec backend python manage.py migrate --noinput
docker compose exec backend python manage.py loaddata intro_course.json
docker compose exec backend python manage.py load_demo_content   # демо-треки (опционально)

# 5. Создать суперюзера для Admin-панели
docker compose exec backend python manage.py createsuperuser
# username: admin, email: admin@admin.com, password: Admin1234!
```

**Проверка:**
- [ ] `http://localhost:8000/healthz` → `{"status": "ok"}`
- [ ] `http://localhost:3000` → открывается главная страница
- [ ] `http://localhost:8000/docs/` → Swagger UI (список эндпоинтов)

### 0.2 Настройка .env для тестирования email

```bash
# В консоли Django видно письма (EMAIL_BACKEND = console).
# Чтобы видеть письма, смотри логи бэкенда:
docker compose logs -f backend
# Оставь этот терминал открытым — туда будут падать verification-письма.
```

### 0.3 Инструменты для тестирования WS

- Браузер DevTools (F12) → Network → WS — для наблюдения за сокетом
- Postman / Bruno — для прямых API-запросов
- `wscat` (npm i -g wscat) — для ручного теста WebSocket

---

## 1. Регистрация и активация Email

### 1.1 Создание аккаунта

1. Открыть `http://localhost:3000/register`
2. Заполнить: `username=testuser1`, `email=test@test.com`, `password=Test1234`
3. Нажать «Зарегистрироваться»

**Ожидается:**
- [ ] Toast «Аккаунт создан! Проверь почту — мы отправили ссылку для активации.»
- [ ] Редирект на `/login?pending_verify=test%40test.com`
- [ ] В логах бэкенда (`docker compose logs -f backend`) появляется письмо с URL вида:
  ```
  http://localhost:3000/verify-email?uid=MTY&token=c5q...
  ```

### 1.2 Логин до активации

1. На странице `/login` ввести `testuser1` / `Test1234`
2. Нажать «Войти»

**Ожидается:**
- [ ] HTTP 401, toast «No active account found with the given credentials»
- [ ] Страница `/login` остаётся, токен в localStorage **не** появляется

### 1.3 Активация по ссылке

1. Скопировать из логов бэкенда URL: `http://localhost:3000/verify-email?uid=...&token=...`
2. Вставить в браузер, открыть

**Ожидается:**
- [ ] Страница `verify-email.js` показывает «Расшифровка свитка...» (лоадинг)
- [ ] Через 1–2 сек переходит в «Путь открыт!» с иконкой ShieldCheck
- [ ] Toast «Магическая печать снята! Добро пожаловать.»
- [ ] Через 3 сек автоматический редирект на `/login`

### 1.4 Повторная активация (та же ссылка)

1. Снова открыть ту же ссылку `/verify-email?uid=...&token=...`

**Ожидается:**
- [ ] Страница показывает «Темная магия вмешалась»
- [ ] Текст ошибки «Invalid token» или «Свиток поврежден или уже использован»
- [ ] Токен одноразовый — повторно не работает

### 1.5 Логин после активации

1. Перейти на `/login`, ввести `testuser1` / `Test1234`

**Ожидается:**
- [ ] HTTP 200, токены появляются в `localStorage.access_token` и `localStorage.refresh_token`
- [ ] Редирект на `/worlds` или `/class`

---

## 2. JWT-аутентификация

### 2.1 Получение токенов

```bash
curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser1","password":"Test1234"}' | python3 -m json.tool
```

**Ожидается:**
- [ ] HTTP 200
- [ ] Тело содержит `"access"` и `"refresh"` токены
- [ ] Сохрани `access` в переменную: `ACCESS=$(curl ... | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")`

### 2.2 Доступ к защищённому ресурсу

```bash
curl -s http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer $ACCESS" | python3 -m json.tool
```

**Ожидается:**
- [ ] HTTP 200
- [ ] JSON с `username`, `email`, `profile.xp`, `profile.level`

### 2.3 Запрос без токена

```bash
curl -s http://localhost:8000/api/auth/me/
```

**Ожидается:**
- [ ] HTTP 401 `{"detail": "Authentication credentials were not provided."}`

### 2.4 Обновление access-токена

```bash
REFRESH="<вставь refresh из 2.1>"
curl -s -X POST http://localhost:8000/api/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d "{\"refresh\":\"$REFRESH\"}" | python3 -m json.tool
```

**Ожидается:**
- [ ] HTTP 200
- [ ] Новый `"access"` токен (отличается от предыдущего)

### 2.5 Logout (blacklist refresh)

1. Открыть `/profile` в браузере, нажать «Выйти»

**Ожидается:**
- [ ] `localStorage.access_token` и `localStorage.refresh_token` удалены (проверь в DevTools → Application → LocalStorage)
- [ ] Редирект на `/login`
- [ ] Попытка использовать старый refresh → HTTP 401 «Token is blacklisted»

---

## 3. Выбор Класса (блокировка до прохождения вводного курса)

### 3.1 Новый пользователь → класс заблокирован

1. Залогиниться как `testuser1` (только что зарегистрированный)
2. Открыть `http://localhost:3000/class`

**Ожидается:**
- [ ] Экран «Класс заблокирован» — НЕ показывает карточки Маг/Рыцарь
- [ ] Есть ссылка/кнопка «Пройти вводный курс» → ведёт на `/missions/1` или `/worlds`

### 3.2 API статуса блокировки

```bash
curl -s http://localhost:8000/api/game/intro-status/ \
  -H "Authorization: Bearer $ACCESS" | python3 -m json.tool
```

**Ожидается:**
- [ ] `"class_unlocked": false`
- [ ] `"completed": 0`, `"total": 4` (или аналогичный счётчик прогресса по вводному треку)

### 3.3 После прохождения всех 4 миссий вводного курса (проверь позже, после раздела 4)

```bash
curl -s http://localhost:8000/api/game/intro-status/ \
  -H "Authorization: Bearer $ACCESS" | python3 -m json.tool
```

**Ожидается:**
- [ ] `"class_unlocked": true`

### 3.4 Выбор класса (после разблокировки)

1. Открыть `/class` — теперь должны быть видны карточки «Маг» и «Рыцарь»
2. Выбрать один из классов

**Ожидается:**
- [ ] Toast «Путь Мага принят!» (или «Рыцаря»)
- [ ] В `/profile` в поле класса отображается выбранный
- [ ] `/worlds` показывает карту с темой класса (другой фон/цвета)

---

## 4. Прохождение Миссии (Story → Quiz → Code)

> Используй миссию 1 из вводного трека (`/missions/1`)

### 4.1 Загрузка миссии

1. Открыть `http://localhost:3000/missions/1`

**Ожидается:**
- [ ] Заголовок миссии виден (не «undefined», не пустой)
- [ ] Stepper показывает 3 шага: Story / Quiz / Code
- [ ] Текущий шаг подсвечен

### 4.2 Story-шаг

1. Прочитать историю, нажать «Материал усвоен» (или аналог)

**Ожидается:**
- [ ] Шаг отмечается ✓
- [ ] Автоматически или по кнопке переход на Quiz

### 4.3 Quiz — неверный ответ

1. Выбрать заведомо **неправильный** вариант ответа
2. Нажать «Произнести ответ» (или «Проверить»)

**Ожидается:**
- [ ] Toast «Ответ неверный!» (красный)
- [ ] Прогресс **не** продвигается (шаг не отмечается ✓)
- [ ] XP **не** начисляется

### 4.4 Quiz — верный ответ

1. Выбрать правильный вариант
2. Нажать «Произнести ответ»

**Ожидается:**
- [ ] Toast «Верно!» (зелёный)
- [ ] Шаг ✓, переход на Code
- [ ] В `/profile` XP немного вырос

### 4.5 Code-редактор

1. На шаге Code должен открыться редактор

**Ожидается:**
- [ ] Starter-код отображается с подсветкой синтаксиса
- [ ] Номера строк видны
- [ ] Кнопки «Run», «Stop», предметы инвентаря (если есть)

### 4.6 Успешный запуск кода

1. Если starter-код не проходит тест — напиши простой правильный вариант
2. Нажать «Run»

**Ожидается:**
- [ ] Терминал (xterm.js) появляется и стримит вывод
- [ ] Зелёный «✔ Тест пройден» в терминале
- [ ] Миссия завершается, XP начисляется

### 4.7 Ошибка в коде

1. Намеренно написать код с синтаксической ошибкой: `print("hi`
2. Нажать «Run»

**Ожидается:**
- [ ] Терминал показывает красный stderr (`SyntaxError: ...`)
- [ ] Миссия **не** завершается
- [ ] Кнопка «Run» снова доступна

### 4.8 Завершение миссии

1. Успешно завершить все 3 шага миссии 1

**Ожидается:**
- [ ] Toast «Легендарный квест завершён!» (или аналог)
- [ ] XP в профиле увеличился
- [ ] На карте мира миссия 1 отображается как пройденная (CheckCircle-иконка)

> **Повтори шаги 4.1–4.8 для миссий 2, 3, 4** чтобы пройти весь вводный курс и разблокировать класс (нужно для раздела 3.3).

---

## 5. WebSocket-терминал (Docker-sandbox)

### 5.1 Установка WS-соединения

1. Открыть code-задачу в браузере
2. Открыть DevTools (F12) → Network → вкладка WS

**Ожидается:**
- [ ] Присутствует соединение `ws://localhost:8000/ws/runner/?token=<JWT>`
- [ ] Статус: 101 Switching Protocols

### 5.2 Стриминг вывода (не буферизация)

1. Написать код:
   ```python
   import time
   for i in range(5):
       print(i)
       time.sleep(0.5)
   ```
2. Нажать «Run»

**Ожидается:**
- [ ] Числа 0, 1, 2, 3, 4 появляются в терминале **по одному** с задержкой 0.5 сек каждое
- [ ] **Не** все сразу в конце (иначе стриминг сломан)

### 5.3 Кнопка Stop

1. Написать бесконечный цикл:
   ```python
   while True:
       print("running...")
       import time; time.sleep(0.1)
   ```
2. Нажать «Run», дождаться нескольких строк вывода
3. Нажать «Stop»

**Ожидается:**
- [ ] Поток вывода прекращается
- [ ] В терминале сообщение об остановке («stopped» / «killed» / аналог)
- [ ] Кнопка «Run» снова становится активной

### 5.4 Анонимный WS-запрос

```bash
# Попробовать подключиться без токена
wscat -c "ws://localhost:8000/ws/runner/"
# или
wscat -c "ws://localhost:8000/ws/runner/?token=invalid_token"
```

**Ожидается:**
- [ ] Соединение закрывается с кодом 4401 (Unauthorized)

### 5.5 Таймаут 15 секунд

1. Запустить код:
   ```python
   import time; time.sleep(30)
   print("never")
   ```
2. Подождать ~15–17 сек

**Ожидается:**
- [ ] Контейнер убивается автоматически через ~15 сек
- [ ] В терминале сообщение о превышении лимита

---

## 6. Инвентарь и AI Summon

> Предварительно добавь предметы в инвентарь через Django Admin или напрямую:
> `docker compose exec backend python manage.py shell -c "from users.models import Profile; p = Profile.objects.get(user__username='testuser1'); p.ai_summons=5; p.hint_scrolls=5; p.skeleton_scrolls=5; p.save()"`

### 6.1 Счётчики предметов в UI

1. Открыть code-задачу

**Ожидается:**
- [ ] Рядом с кнопками предметов видны числа (5/5/5 после shell-команды выше)

### 6.2 Свиток-скелет (skeleton_scroll — Boilerplate)

1. Нажать кнопку «Свиток Архитектора» (skeleton scroll)

**Ожидается:**
- [ ] В редактор вставляется boilerplate-код для задачи
- [ ] Счётчик `skeleton_scrolls` уменьшился на 1 (видно в UI и в `/profile`)

### 6.3 Свиток подсказки (hint_scroll)

1. Нажать кнопку «Зелье Ясности» (hint scroll)

**Ожидается:**
- [ ] Toast или всплывающее окно с текстовой подсказкой к задаче
- [ ] Счётчик `hint_scrolls` -1

### 6.4 AI Summon (GEMINI_API_KEY должен быть задан!)

> Если GEMINI_API_KEY не задан, кнопка должна быть disabled или вернёт graceful error.
>
> Чтобы задать: `docker compose exec backend sh -c "export GEMINI_API_KEY=ключ"`
> (или пропиши в .env и перезапусти backend)

1. Написать частично неверный код
2. Нажать кнопку «AI Summon» (ai_summons)

**Ожидается:**
- [ ] В терминале появляется цветной блок:
  ```
  ╔══ 🤖 Мудрец говорит ══╗
  ║ [текст подсказки от Gemini]
  ╚═══════════════════════╝
  ```
- [ ] Цвет текста пурпурный (`\x1b[35m`)
- [ ] Счётчик `ai_summons` -1

### 6.5 Rate-limiting AI (10 req/min)

> Только если GEMINI_API_KEY задан

1. Сделать 11 запросов к AI Summon за 1 минуту

**Ожидается:**
- [ ] 11-й запрос возвращает HTTP 429
- [ ] Toast «Слишком много запросов к Мудрецу»

### 6.6 Предмет при 0 штук

1. Потратить все предметы одного типа (или вручную через shell: `p.ai_summons=0; p.save()`)
2. Попытаться нажать кнопку

**Ожидается:**
- [ ] Кнопка disabled (серая, не кликается)
- [ ] Действие не выполняется

---

## 7. Профиль

### 7.1 Загрузка профиля

1. Открыть `http://localhost:3000/profile`

**Ожидается:**
- [ ] Username отображается (не «undefined», не «Не указан»)
- [ ] Email отображается (не «undefined», не «Не указан»)
- [ ] Уровень (Level X)
- [ ] XP-бар виден
- [ ] Кнопки «Редактировать», «Сменить класс», «Выйти» присутствуют

### 7.2 Редактирование username

1. Нажать «Редактировать»
2. Изменить username на `testuser1_edited`
3. Нажать «Сохранить»

**Ожидается:**
- [ ] Toast «Данные профиля успешно обновлены!»
- [ ] Режим редактирования закрывается
- [ ] На странице профиля новый username отображается

### 7.3 Сброс класса

1. Нажать «Сменить класс»

**Ожидается:**
- [ ] Toast «Класс успешно сброшен. Выберите новый путь!»
- [ ] Редирект на `/class`

### 7.4 Level-up (проверь после набора XP)

После прохождения нескольких миссий:
- [ ] В профиле XP-бар изменился
- [ ] Если XP достиг максимума уровня — Level увеличился

---

## 8. Лидерборд

1. Открыть `http://localhost:3000/leaderboard`

**Ожидается:**
- [ ] Список игроков загружается (не пустой, если есть пользователи)
- [ ] Переключатель «Всё время / Неделя» — при смене список обновляется
- [ ] Кнопка «Обновить» (Refresh) обновляет список без перезагрузки страницы
- [ ] Топ-3 подсвечены: 🥇 золото / 🥈 серебро / 🥉 бронза
- [ ] Твой аккаунт выделен или маркирован «(ты)»

---

## 9. Локализация (i18n)

1. Переключить язык RU → EN (кнопка в меню/header)

**Ожидается:**
- [ ] Навигационные пункты меняются на английский
- [ ] Заголовки страниц (Login, Register, Profile, Worlds) — на EN
- [ ] Кнопки и подписи — на EN

2. Переключить EN → RU

**Ожидается:**
- [ ] Всё возвращается на русский

3. Выбрать EN → перезагрузить страницу (F5)

**Ожидается:**
- [ ] Язык остался EN (сохранён в localStorage)

4. Открыть `/missions/1` и переключить язык

**Ожидается:**
- [ ] Если у миссии есть `en_title`/`en_description` — отображается английский контент
- [ ] Если нет перевода — fallback на русский (не пустое поле)

---

## 10. Карта Мира

### 10.1 Основная карта

1. Открыть `http://localhost:3000/worlds`

**Ожидается:**
- [ ] Карта с узлами-миссиями загружается
- [ ] Анимация пути между узлами проигрывается
- [ ] Загрузка не бесконечная (нет spinner после 3 сек)

### 10.2 Статусы узлов

На карте должны быть узлы трёх состояний:
- [ ] 🔒 Заблокированный (Lock-иконка) — prerequisite не выполнен
- [ ] ✅ Пройденный (CheckCircle) — миссия завершена
- [ ] ▶ Доступный (без иконки или Play) — можно начать

### 10.3 Тема карты по классу

1. Выбрать класс «Маг» → открыть `/worlds`
2. Выбрать класс «Рыцарь» → открыть `/worlds`

**Ожидается:**
- [ ] Визуально разные фоны/цвета карты для разных классов
- [ ] Без выбранного класса — дефолтная тема

---

## 11. Django Admin (для методолога)

1. Открыть `http://localhost:8000/admin/`
2. Войти как `admin` / `Admin1234!` (или твой суперюзер)

### 11.1 Управление треками

1. Перейти в **Game → Tracks**

**Ожидается:**
- [ ] Список треков загружается
- [ ] Видны колонки: название (RU), название (EN), порядок, is_intro
- [ ] Фильтры и поиск работают
- [ ] Трек «Основы Python» присутствует (из `intro_course.json`) с `is_intro=✓`

2. Открыть трек → изменить `ru_title` → сохранить

**Ожидается:**
- [ ] Изменение сохраняется без ошибок

### 11.2 Управление миссиями

1. **Game → Missions**
2. Открыть миссию 1

**Ожидается:**
- [ ] Видны поля: RU/EN заголовки, описание, XP-награда, prerequisites
- [ ] Секция «Mission Tasks» показывает 3 задачи (Story/Quiz/Code) с inline-формами
- [ ] Можно добавить новую задачу через inline

### 11.3 Цвет-бейджи задач

В списке `Mission Tasks`:
- [ ] `code` задачи — синий бейдж
- [ ] `quiz` задачи — оранжевый бейдж
- [ ] `story` задачи — бирюзовый бейдж

### 11.4 Поиск

1. В поиске написать «Python»

**Ожидается:**
- [ ] Возвращаются треки/миссии с «Python» в названии

---

## 12. Кастомная 404

1. Открыть `http://localhost:3000/completely-random-nonexistent-url-12345`

**Ожидается:**
- [ ] Показывается RPG-стилизованная страница 404 (не стандартная Next.js)
- [ ] Текст «Эта тропа ведёт в забвение» или аналогичный тематический
- [ ] Кнопка «Вернуться на карту мира» → ведёт на `/worlds`

---

## 13. Health Check и API документация

```bash
# Health endpoint
curl http://localhost:8000/healthz
# Ожидается: {"status": "ok"}

# Swagger UI
open http://localhost:8000/docs/
# Ожидается: интерактивная документация API

# ReDoc
open http://localhost:8000/redoc/
```

- [ ] `healthz` возвращает 200 `{"status": "ok"}`
- [ ] Swagger показывает все эндпоинты (auth, game, profile)
- [ ] ReDoc открывается

---

## 14. Нагрузка и безопасность (мини-чеклист)

### 14.1 Инъекция в код (security)

1. В терминале написать:
   ```python
   import subprocess; subprocess.run(["curl", "https://evil.com"])
   ```

**Ожидается:**
- [ ] Ошибка в терминале (нет сети внутри sandbox-контейнера)
- [ ] ИЛИ команда выполняется, но не имеет доступа к интернету (network=none)

### 14.2 Параллельные запросы Run

1. Быстро нажать «Run» два раза подряд

**Ожидается:**
- [ ] Второй запрос отклоняется с «run in progress» или аналогом
- [ ] Не запускаются два контейнера одновременно

### 14.3 CORS

```bash
curl -H "Origin: https://evil.com" \
  -H "Authorization: Bearer $ACCESS" \
  http://localhost:8000/api/auth/me/
```

**Ожидается:**
- [ ] Запрос проходит (CORS_ALLOW_ALL_ORIGINS=True в dev — это нормально)
- [ ] **ВАЖНО:** На production CORS должен быть ограничен вашим доменом! (см. раздел 15)

---

## 15. Чеклист перед деплоем на сервер

Пройди этот список **перед** запуском `docker compose up` на VPS:

### Переменные окружения (.env на сервере)

```
SECRET_KEY=<минимум 50 случайных символов — НЕ "dev-secret">
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
FRONTEND_URL=https://yourdomain.com

POSTGRES_DB=rpgdb
POSTGRES_USER=<не rpguser>
POSTGRES_PASSWORD=<сложный пароль>

GEMINI_API_KEY=<твой ключ Gemini>

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<твой email>
EMAIL_HOST_PASSWORD=<app password>
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

CORS_ALLOWED_ORIGINS=https://yourdomain.com
```

**Чеклисты:**
- [ ] `SECRET_KEY` сгенерирован (`python -c "from django.core.utils.crypto import get_random_string; print(get_random_string(60))"`)
- [ ] `DEBUG=False`
- [ ] `ALLOWED_HOSTS` содержит твой домен
- [ ] `FRONTEND_URL` содержит https-адрес (без `/` в конце)
- [ ] Email бэкенд настроен на SMTP (не console)
- [ ] `CORS_ALLOWED_ORIGINS` ограничен твоим доменом (не ALLOW_ALL)
- [ ] Пароли PostgreSQL изменены
- [ ] `GEMINI_API_KEY` задан

### Команды после первого запуска

```bash
# На сервере, после docker compose up -d:
docker compose exec backend python manage.py migrate --noinput
docker compose exec backend python manage.py collectstatic --noinput
docker compose exec backend python manage.py loaddata intro_course.json
docker compose exec backend python manage.py createsuperuser
```

- [ ] Миграции применены без ошибок
- [ ] Статика собрана
- [ ] Вводный курс загружен
- [ ] Суперюзер создан (с надёжным паролем!)

### Nginx + SSL

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;
    server_name yourdomain.com;
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend (Next.js)
    location / {
        proxy_pass http://localhost:3000;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
    }

    # WebSocket для терминала
    location /ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }

    # Django Admin + Swagger
    location ~ ^/(admin|docs|redoc|static|healthz) {
        proxy_pass http://localhost:8000;
    }
}
```

```bash
# Получить SSL через Let's Encrypt:
certbot --nginx -d yourdomain.com
```

- [ ] Nginx настроен
- [ ] SSL-сертификат получен и автообновление включено (`certbot renew --dry-run`)
- [ ] WS-апгрейд прописан в nginx (без него терминал не работает!)

### Финальная проверка на продакшене

```bash
# Заменить yourdomain.com на свой
curl https://yourdomain.com/healthz              # {"status": "ok"}
curl https://yourdomain.com/api/auth/register/   # 405 (только POST)
curl https://yourdomain.com/api/docs/            # 200 Swagger
```

- [ ] HTTPS работает (замок в браузере)
- [ ] HTTP редиректит на HTTPS
- [ ] `healthz` возвращает 200
- [ ] WebSocket терминал работает на `wss://` (не `ws://`)

---

## 🎯 Критический путь для демо комиссии (15 минут)

Это минимальный сценарий, который нужно пройти **без ошибок** перед защитой:

```
1. Открыть /register → зарегистрироваться (новый email)
2. Скопировать verify-email ссылку из логов бэкенда → открыть
3. Страница "Путь открыт!" → автоматический редирект на /login
4. Залогиниться → попасть на /class (заблокирован)
5. /missions/1 → пройти Story → Quiz → Code (Run + успешный тест)
6. Повторить для миссий 2, 3, 4 (вводный трек)
7. /class → классы разблокированы → выбрать Мага
8. /worlds → карта с темой Мага, миссии 1-4 отмечены ✓
9. Открыть миссию 5 → нажать AI Summon → ответ в терминале
10. /profile → username и email отображаются, XP/Level видны
11. /leaderboard → список игроков
12. Сменить язык EN → заголовки на английском
13. /admin/ → зайти как superuser, открыть миссию 1
```

**Если всё прошло без красных toast-ов и 500-х ошибок — проект готов к защите. ✅**

---

*Дата создания: 2026-05-21 | Версия проекта: v1.0 (diploma defense)*
