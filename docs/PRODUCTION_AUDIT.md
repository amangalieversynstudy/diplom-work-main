# RPG Academy — Аудит заглушек и production-готовности

> Документ составлен 2026-05-22 после прохождения QA по модулям 4 и 8.
> Используй как чек-лист для зачистки перед демо/production.

---

## 🚨 Критические заглушки (CRIT)

### CRIT-01 — Платежи полностью фейковые
**Файл:** `frontend/pages/api/payments/checkout.js`
```js
const intentId = `fake_intent_${Date.now()}`;
message: "Оплата смоделирована. Доступ открыт на 30 дней.";
```
- Это Next.js API-роут, который возвращает `success: true` без реальной обработки
- Никакой реальной интеграции со Stripe/ЮKassa/CloudPayments нет
- Премиум-доступ выдаётся **бесплатно любому, кто нажмёт кнопку**

**Чтобы продакшнить:** интегрировать настоящий PSP (Stripe Checkout / ЮKassa), вебхуки на backend, модель `Subscription` в Django.

---

### CRIT-02 — Email backend = console
**Файл:** `backend/core/settings/base.py:152-153`
```python
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
```
- По умолчанию письма верификации **печатаются в логи**, а не отправляются
- В QA-чеклисте есть инструкция `docker compose logs backend | grep verify-email` — это и есть workaround вокруг этой заглушки
- В production `EMAIL_BACKEND` нужно переопределить в env на SMTP (или Sendgrid/SES/etc)

**Чтобы продакшнить:** установить `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` в `.env.prod` + настроить реальный SMTP.

---

### CRIT-03 — Backend отправляет `leveled_up`, фронт игнорирует
**Файл:** `backend/game/views.py:196`
```python
"leveled_up": leveled_up,  # Триггер для салюта на клиенте!
```
- Backend честно считает level-up и отправляет флаг
- Фронтенд **нигде не читает** ни `leveled_up`, ни `xp_added`, ни `new_level`
- Это ломает TC-RANK-02 («toast level up») из QA-чеклиста
- Также нет анимации заполнения XP-полосы при получении опыта

**Чтобы исправить:** в `handleCompleteTask` (миссии) и `Missions.complete` обработать ответ — показать toast «🎉 Уровень повышен! Level X», запустить конфетти.

---

## 🟡 Серьёзные пробелы (HIGH)

### HIGH-01 — Rank-модель оторвана от Profile
**Файлы:** `backend/users/models.py`, `backend/users/serializers.py`
- `game.Rank` существует со slug/title/min_level/min_xp
- Но `Profile` не имеет поля `rank` или `current_rank`
- API `/profile/me/` не возвращает текущий ранг — фронт не может показать «Новичок / Ученик / Маг»
- TC-RANK-01 из QA-чеклиста **никогда не пройдёт** в текущей реализации

**Чтобы исправить:** добавить `Profile.get_rank()` property или `current_rank` SerializerMethodField, который вычисляет ранг из `level` через `Rank.objects.filter(min_level__lte=level).order_by('-min_level').first()`.

---

### HIGH-02 — XPBar показывал неправильный прогресс ✅ FIXED
**Файл:** `frontend/pages/profile.jsx:151` + `frontend/components/XPBar.jsx`
- ~~Родитель передавал `currentXP/maxXP`, компонент ждал `current/max`~~
- ~~`maxXP = level * 1000`, хотя бэкенд использует 100 XP на уровень~~
- **Исправлено в текущем коммите**

---

### HIGH-03 — Leaderboard entries не создаются автоматически
**Файл:** `backend/game/models.py:331`
- Модель `LeaderboardEntry` есть, ViewSet есть, но **никто никогда не создаёт записи**
- При начислении XP в `add_xp()` не происходит обновление leaderboard
- `/leaderboard/` всегда возвращает пустой список → TC-LEAD-01 «Сообщение Пока пусто» — это и есть основной сценарий, не edge case

**Чтобы исправить:** post_save signal на `Progress.complete()` или management команда `python manage.py rebuild_leaderboard`.

---

### HIGH-04 — Soft-lock confirm через `window.confirm()`
**Файл:** `frontend/pages/class.jsx:69`
```js
const confirmChoice = window.confirm("Академия настоятельно...");
```
- Нативный браузерный confirm выглядит чужеродно в RPG-стиле
- Не темизируется, не локализуется, на мобиле — некрасиво
- Для production надо заменить на кастомный модальный диалог в стиле игры

---

### HIGH-05 — `console.log/error` в проде
**Файл:** `frontend/pages/class.jsx:73`
```js
console.error("Ошибка сервера:", e.response?.data);
```
- 5 случаев `console.*` во фронтенде уйдут в production
- Не критично, но засоряет DevTools у пользователей и может протечь чувствительные данные ошибок

**Чтобы исправить:** добавить wrapper `logger.error()`, который пишет только в dev, или Sentry в проде.

---

## 🟢 Качество и UX-нюансы (MID)

### MID-01 — Нет Sentry / error tracking
- В backend нет `sentry-sdk`, во фронте нет `@sentry/nextjs`
- В production ошибки уйдут в никуда
- Особенно важно для runner — там много edge cases

### MID-02 — Нет rate-limiting на login / register endpoints
- `AIAssistView` зарегулирован (10/m)
- `register`, `login`, `password reset` — без лимитов на брутфорс
- В QA TC-SEC-06 ожидает 429 после ~10 запросов, но реализации нет

### MID-03 — JWT refresh без rotation
- `simplejwt` дефолтно не ротирует refresh-токены
- Утёкший refresh = пожизненный доступ
- Включить `ROTATE_REFRESH_TOKENS=True` в settings + `BLACKLIST_AFTER_ROTATION=True`

### MID-04 — Нет проверки CSP / security headers
- Нет `django-csp` или `SecureMiddleware`
- Заголовки `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security` не настроены

### MID-05 — Mission.complete не идемпотентен
- Если пользователь дважды нажмёт «Завершить миссию», XP начислится дважды (если `repeatable=True`)
- Нужен ETag или `request_id` для дедупликации

### MID-06 — Нет инвалидации кэша при смене языка
- `useDictionary()` берёт из localStorage, но если бэкенд вернёт `title_en` после смены языка — миссия не перерендерится
- Нужен `key` на ID языка или явный refetch

### MID-07 — Inventory сбрасывается только дефолтным значением
- При создании Profile инвентарь = `{ai_summons:3, hint_scrolls:5, skeleton_scrolls:3}`
- Нет логики пополнения (награды за level-up, daily quest)
- После исчерпания пользователь застрянет, премиум-механика инвентаря не работает

### MID-08 — Удалена «Древо Навыков» с профиля ✅ FIXED
- Был визуализационный компонент со статусом «MVP» — удалён
- Если позже захочется вернуть — нужна реальная progression-модель, а не статика

---

## 📦 Инфраструктура

### INFRA-01 — `DEBUG=True` по умолчанию в local.py — это правильно
### INFRA-02 — `production.py` использует `DEBUG=False`, `ALLOWED_HOSTS` из env — OK
### INFRA-03 — Нет `docker-compose.prod.yml` — все используют единый compose
### INFRA-04 — Нет healthchecks в docker-compose для всех сервисов (только backend `/healthz`)
### INFRA-05 — Нет CI/CD — GitHub Actions не настроены
### INFRA-06 — Нет `.env.example` с актуальным списком переменных
### INFRA-07 — Бэкенд использует Daphne — нужен `--workers` или Gunicorn для multi-CPU
### INFRA-08 — PostgreSQL без backup-стратегии

---

## ✅ Что готово хорошо

- Auth-флоу (JWT, refresh, email verify) — солидный
- Sandbox-runner для Python через WS — отличная архитектура
- Тестовое покрытие backend — есть тесты для auth, profile, missions, runner WS
- ORM-оптимизации (select_related, prefetch_related) — добавлены везде, где надо
- Skill-tree UX свободной смены класса — реализован чисто
- Структура settings (base/local/production/test) — по best practice

---

## 🎯 Приоритеты перед демо

| Приоритет | Что делать | Время |
|---|---|---|
| 🔴 P0 | CRIT-03 (level-up toast) — самая видимая дырка | 30 мин |
| 🔴 P0 | HIGH-01 (Rank в Profile) — TC-RANK-01 сейчас падает | 45 мин |
| 🟡 P1 | HIGH-03 (leaderboard signal) | 1 час |
| 🟡 P1 | HIGH-04 (заменить window.confirm) | 1 час |
| 🟡 P1 | CRIT-02 (real SMTP) — если нужна live-демонстрация регистрации | 30 мин |
| 🟢 P2 | Остальное — после демо |

**CRIT-01 (платежи)** — для демо можно оставить заглушку, но в `PaywallModal` явно сказать «Демо-режим». Для production — критично.
