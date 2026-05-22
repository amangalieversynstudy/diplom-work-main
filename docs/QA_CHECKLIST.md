# RPG Academy — Полный чек-лист ручного тестирования

> **Метки:** ✅ прошло · ❌ упало (добавь заметку) · ⚠️ частично
>
> Полный прогон ~3 часа. Минимум перед демо — все P0 (~25 кейсов, 1.5–2 ч).

---

## 0. Тестовые данные

### 0.1 Учётные записи в базе

| Username | Password | Email | Активен | Заметки |
|---|---|---|---|---|
| `admin` | `Admin1234!` | — | ✅ | Superuser, доступ к `/admin/` |
| `smoketest` | `SmokeTest123!` | smoke@test.com | ✅ | Маг Кода, level 1, есть bio |
| `smoke3` | `SmokeTest123!` | smoke3@test.com | ✅ | Чистый аккаунт |

### 0.2 Реквизиты для новых регистраций

```
Username: test_qa_01   Email: qa01@test.com   Password: QaPass2026!
Username: test_qa_02   Email: qa02@test.com   Password: QaPass2026!
Username: test_qa_03   Email: qa03@test.com   Password: QaPass2026!
```

### 0.3 ID миссий и треков

| Тип | ID | Название |
|---|---|---|
| Track | 1 | Intro Course (RU) / Introductory Course (EN) |
| Mission | 1 | Доступна сразу (no prereq) |
| Mission | 2–5 | Заблокированы, нужны prerequisites |
| Rank | 1–5 | Новичок → Великий Волшебник |
| ClassRole | 1 | Маг Кода |
| ClassRole | 2 | Рыцарь Логики |
| ClassRole | 3 | Друид Данных |

### 0.4 Тестовый Python-код для code-заданий

```python
# Простой
print("Hello RPG")

# С математикой
result = sum(range(1, 11))
print(result)  # 55

# С условием
n = 7
print("even" if n % 2 == 0 else "odd")

# Ошибка для проверки stderr
print(undefined_var)

# Бесконечный цикл (для проверки таймаута)
while True: pass
```

### 0.5 Полезные команды

```bash
# Активировать пользователя без email-флоу
docker compose exec backend python manage.py shell -c "
from users.models import User
u = User.objects.get(username='ТВОЙ_USERNAME')
u.is_active = True; u.save()
print('активирован')
"

# Получить verify-link из логов
docker compose logs backend 2>&1 | grep "verify-email" | tail -3

# Создать суперюзера
docker compose exec backend python manage.py createsuperuser

# Перезагрузить фикстуры
docker compose exec backend python manage.py loaddata ranks class_roles intro_course

# Сброс XP/level пользователя
docker compose exec backend python manage.py shell -c "
from users.models import User
u = User.objects.get(username='smoketest')
p = u.profile
p.xp = 0; p.level = 1; p.save()
"
```

### 0.6 Запуск окружения

```bash
docker compose up -d db redis backend frontend
docker compose ps                            # все должны быть Up (healthy)
docker compose exec backend python manage.py migrate --noinput
docker compose exec backend python manage.py loaddata intro_course.json
```

Проверка:
- [ ] `http://localhost:8000/healthz` → `{"status":"ok"}`
- [ ] `http://localhost:3000` → главная открывается
- [ ] `http://localhost:8000/docs/` → Swagger UI

---

## 🔐 Модуль 1: Регистрация и активация

### TC-AUTH-01 Успешная регистрация — 🔴 P0
- [ ] Открой `/register`
- [ ] Введи `test_qa_01 / qa01@test.com / QaPass2026!`
- [ ] Жми «Присоединиться»

Ожидается:
- [ ] Toast «Регистрация успешна»
- [ ] Редирект на `/profile` (или `/login?pending_verify=…` если prod)
- [ ] В логах backend → `POST /api/auth/register/ 201`

### TC-AUTH-02 Регистрация с занятым username — 🔴 P0
- [ ] `/register` → `smoketest / новый_email / пароль`
- [ ] Toast с ошибкой / поле подсвечивается, backend → 400

### TC-AUTH-03 Регистрация с занятым email — 🔴 P0
- [ ] `/register` → `новый_username / smoke@test.com / пароль`
- [ ] Ошибка «Email уже используется»

### TC-AUTH-04 Короткий пароль — 🟡 P1
- [ ] `/register` → `новый / новый_email / 123`
- [ ] Ошибка валидации (пароль слишком короткий)

### TC-AUTH-05 Пустые поля — 🟡 P1
- [ ] Жми «Присоединиться» с пустой формой
- [ ] HTML5-валидация или backend 400

### TC-AUTH-06 Email-верификация — 🔴 P0
- [ ] Возьми ссылку: `docker compose logs backend | grep verify-email`
- [ ] Открой `/verify-email?uid=…&token=…`
- [ ] Экран «Магическая печать снята»
- [ ] Через 3 сек редирект на `/login`
- [ ] Toast «Магическая печать снята! Добро пожаловать»

### TC-AUTH-07 Битый токен — 🟡 P1
- [ ] `/verify-email?uid=Ng&token=BROKEN`
- [ ] Экран «Тёмная магия вмешалась»
- [ ] Кнопка «Вернуться к таверне»

### TC-AUTH-08 Ссылка без параметров — 🟢 P2
- [ ] `/verify-email`
- [ ] Ошибка «Ссылка повреждена»

---

## 🔑 Модуль 2: Логин / Логаут

### TC-LOGIN-01 Логин по username — 🔴 P0
- [ ] `/login` → `smoketest / SmokeTest123!`
- [ ] Toast «Добро пожаловать», редирект на `/profile`
- [ ] В localStorage: `access_token`, `refresh_token`

### TC-LOGIN-02 Логин по email — 🔴 P0
- [ ] `/login` → `smoke@test.com / SmokeTest123!`
- [ ] Тот же эффект

### TC-LOGIN-03 Неверный пароль — 🔴 P0
- [ ] `/login` → `smoketest / WRONG`
- [ ] Toast 401, без редиректа

### TC-LOGIN-04 Неактивный аккаунт — 🟡 P1
- [ ] Зарегистрируй нового, НЕ активируй
- [ ] Залогиниться → «No active account»

### TC-LOGIN-05 Logout — 🔴 P0
- [ ] `/profile` → «Выйти»
- [ ] Редирект на `/login`, localStorage очищен
- [ ] Попытка зайти на `/profile` → редирект `/login`

### TC-LOGIN-06 Авто-refresh — 🟡 P1
- [ ] Залогинься, удали `access_token` в DevTools (оставь refresh)
- [ ] Перейди на страницу с API-запросом
- [ ] В Network: запрос `/auth/jwt/refresh/`, страница загружена

### TC-LOGIN-07 Истекший refresh — 🟢 P2
- [ ] Удали оба токена → `/profile` → редирект `/login`

---

## 👤 Модуль 3: Профиль

### TC-PROF-01 Просмотр — 🔴 P0
- [ ] `/profile`: имя героя, уровень, XP-полоса, «Сменить класс», «Выйти»
- [ ] Секция «Настройки аккаунта»: логин и email
- [ ] НЕТ «Неизвестный» / «Не указан»

### TC-PROF-02 Редактирование — 🔴 P0
- [ ] «Редактировать» → username `smoketest_v2` → «Сохранить»
- [ ] Toast «Данные обновлены», username новый
- [ ] Backend: `PATCH /api/profile/me/ 200`

### TC-PROF-03 Username занят — 🔴 P0
- [ ] Редактирование → username `admin`
- [ ] Toast «Такое имя уже занято», backend 400

### TC-PROF-04 Изменение email — 🟡 P1
- [ ] Редактирование → email `new@test.com`
- [ ] Сохранение OK, email обновился

### TC-PROF-05 Отмена редактирования — 🟢 P2
- [ ] Редактирование → «Отмена» → возврат без сохранения

### TC-PROF-06 Кастомный курсор — 🟡 P1
- [ ] Подвигай мышью: зелёный кружок следует
- [ ] Hover на кнопку: кольцо расширяется
- [ ] Alt+Tab → родной курсор; возврат → кастомный

---

## 🧙 Модуль 4: Выбор класса

### TC-CLASS-01 Страница класса — 🔴 P0
- [ ] «Сменить класс» → `/class`
- [ ] 3 карточки: Маг Кода / Рыцарь Логики / Друид Данных
- [ ] Если intro не пройден — экран «Сначала пройди Вводный Курс»

### TC-CLASS-02 Выбор класса — 🔴 P0
- [ ] Клик «Маг Кода»
- [ ] Редирект на `/profile`
- [ ] В UI выбранный класс, backend: `class_role: 1`

### TC-CLASS-03 Смена класса — 🟡 P1
- [ ] Снова «Сменить класс» → «Рыцарь Логики»
- [ ] `class_role` изменён

### TC-CLASS-04 Анимации — 🟢 P2
- [ ] Hover на карточку: scale / glow

---

## 🗺️ Модуль 5: Карта миров

### TC-WORLDS-01 Загрузка — 🔴 P0
- [ ] `/worlds`: видна карта
- [ ] Узлы миссий пульсируют
- [ ] Тропа между узлами (SVG)

### TC-WORLDS-02 Hover — 🟡 P1
- [ ] Раскрывается название, scale 1.1, glow

### TC-WORLDS-03 Клик на доступную — 🔴 P0
- [ ] Клик на первую миссию → `/missions/1`

### TC-WORLDS-04 Клик на locked — 🟡 P1
- [ ] Ничего не происходит, `cursor-default`

### TC-WORLDS-05 Горизонтальный скролл — 🟡 P1
- [ ] Прокрути колёсиком — карта скроллится горизонтально

### TC-WORLDS-06 Пустая карта — 🟢 P2
- [ ] Удали миссии в админке → `/worlds` → сообщение «Пираты украли карту»

---

## ⚔️ Модуль 6: Прохождение миссии

### TC-MISS-01 Открытие — 🔴 P0
- [ ] `/missions/1`: заголовок, степпер слева, контент справа

### TC-MISS-02 Story — 🔴 P0
- [ ] Прочти текст → «Завершить»
- [ ] Переход к следующему, галочка в степпере

### TC-MISS-03 Quiz — 🔴 P0
- [ ] Выбери ответ → «Отправить»
- [ ] «Правильно!» / «Неправильно», `POST /task-progress/`

### TC-MISS-04 Code базовое — 🔴 P0
- [ ] Введи `print("hello")` → «Запустить»
- [ ] В терминале `hello`
- [ ] `POST /runner/execute/ 200`, output=`hello\n`

### TC-MISS-05 Code с ошибкой — 🟡 P1
- [ ] `print(undefined_var)` → stderr с NameError

### TC-MISS-06 Бесконечный цикл — 🟡 P1
- [ ] `while True: pass` → через ~5 сек таймаут
- [ ] Sandbox-контейнер не висит вечно

### TC-MISS-07 Завершение миссии — 🔴 P0
- [ ] Пройди все 3 задания → «Завершить миссию»
- [ ] +XP в профиле, toast о наградах

### TC-MISS-08 Возврат к незаконченной — 🟡 P1
- [ ] Начни, пройди 1 задание, закрой вкладку
- [ ] Открой снова → состояние сохранилось

### TC-MISS-09 Заблокированная — 🟡 P1
- [ ] `/missions/2` без prereq → 403 / предупреждение

---

## 🎒 Модуль 7: Инвентарь

### TC-INV-01 Стартовый — 🔴 P0
- [ ] Новый юзер → code-задание
- [ ] `hint_scrolls=5`, `ai_summons=3`, `skeleton_scrolls=3`
- [ ] Цвета: зелёный / фиолетовый / жёлтый

### TC-INV-02 Hint Scroll — 🔴 P0
- [ ] Клик → счётчик 5→4
- [ ] Подсказка из `data.hint`

### TC-INV-03 Кончились предметы — 🟡 P1
- [ ] Использовать 5 раз → `cursor-not-allowed` серая
- [ ] Backend → 400 «Недостаточно предметов»

### TC-INV-04 AI Summon (Gemini) — 🟢 P2
> ⚠️ Нужен `GEMINI_API_KEY` в `.env`, перезапуск backend
- [ ] Клик → `ai_summons` 3→2
- [ ] AI-подсказка от Gemini

### TC-INV-05 Skeleton Scroll — 🟡 P1
- [ ] Клик → счётчик 3→2, видишь скелетон-решение

---

## 🏆 Модуль 8: Ранги и XP

### TC-RANK-01 Текущий ранг — 🟡 P1
- [ ] `/profile` показывает «Новичок» (level 1)

### TC-RANK-02 Повышение уровня — 🔴 P0
- [ ] Пройди миссию с XP
- [ ] XP-полоса заполняется
- [ ] 100 XP → level 2, ранг «Ученик», toast level up

### TC-RANK-03 XP-полоса — 🟡 P1
- [ ] Показывает текущий / макс до следующего уровня
- [ ] Анимация заполнения

---

## 🥇 Модуль 9: Лидерборд

### TC-LEAD-01 Открытие — 🟡 P1
- [ ] `/leaderboard`: HTTP 200 даже пустой
- [ ] Сообщение «Пока пусто» если 0 entries

### TC-LEAD-02 Себя в топе — 🟢 P2
- [ ] Если есть entries — твой ник подсвечен

---

## 🌐 Модуль 10: Интернационализация

### TC-I18N-01 Переключение языка — 🟡 P1
- [ ] Переключатель RU/EN в шапке
- [ ] Тексты переведены: Sanctum, Worlds, Quest, Hero
- [ ] Перезагрузка — язык сохраняется (localStorage `ui_language`)

### TC-I18N-02 Перевод миссий — 🟡 P1
- [ ] В EN-режиме миссия с `title_en` / `body_en`

### TC-I18N-03 Fallback на RU — 🟢 P2
- [ ] Если EN нет — показывается RU

---

## 🛠️ Модуль 11: Админка

### TC-ADM-01 Логин — 🔴 P0
- [ ] `/admin/` → `admin / Admin1234!` → войдёшь

### TC-ADM-02 Список миссий — 🟡 P1
- [ ] Game → Missions: 5 миссий с RU/EN
- [ ] Цветные badge типов задач

### TC-ADM-03 Создание миссии — 🔴 P0
- [ ] «+ Add» → location, title_ru, title_en, xp_reward
- [ ] Inline MissionTask → Save
- [ ] На `/worlds` появилась

### TC-ADM-04 Создание задания — 🟡 P1
- [ ] Mission Tasks → «+ Add» → mission, task_type=code, body
- [ ] Поле `data`: `{"language":"python","starter":"# code here"}`
- [ ] Save OK

### TC-ADM-05 Редактирование класса — 🟢 P2
- [ ] Class Roles → «Маг Кода» → изменить description → Save
- [ ] На `/class` обновился

### TC-ADM-06 Создание ранга — 🟢 P2
- [ ] Ranks → «+ Add» → slug, title, min_level, min_xp

---

## 🛡️ Модуль 12: Безопасность

### TC-SEC-01 API без токена — 🔴 P0
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/profile/me/
# Ожидается: 401
```

### TC-SEC-02 Битый токен — 🔴 P0
```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer FAKE" \
  http://localhost:8000/api/profile/me/
# Ожидается: 401
```

### TC-SEC-03 Чужой профиль — 🔴 P0
- [ ] Логин `smoketest` → PATCH `/api/users/<other_id>/`
- [ ] 403 / 404

### TC-SEC-04 SQL-инъекция — 🟡 P1
- [ ] Username `' OR 1=1--`
- [ ] 400, без утечки

### TC-SEC-05 XSS в bio — 🟡 P1
- [ ] В bio: `<script>alert(1)</script>`
- [ ] Сохранилось как текст, alert НЕ срабатывает

### TC-SEC-06 Rate-limit регистрации — 🟡 P1
```bash
for i in {1..20}; do
  curl -s -X POST http://localhost:8000/api/auth/register/ \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"flood$i\",\"email\":\"f$i@x.com\",\"password\":\"X12345678!\"}"
  echo ""
done
# Ожидается: после ~10 запросов HTTP 429
```

### TC-SEC-07 Rate-limit AI Summon — 🔴 P0
```bash
# Получи JWT, потом 12 запросов подряд:
for i in {1..12}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer $JWT" \
    -X POST http://localhost:8000/api/game/ai-assist/ \
    -H "Content-Type: application/json" \
    -d '{"code":"print(1)","task_description":"hello","language":"python"}'
done
# Ожидается: после 10 запросов HTTP 429
```

### TC-SEC-08 Бесконечный цикл в Runner — 🔴 P0
- [ ] `while True: pass` → через 5 сек прерывается
- [ ] Sandbox-контейнер не висит вечно

---

## 📱 Модуль 13: Кросс-браузерность / Mobile

### TC-RESP-01 Mobile viewport — 🟡 P1
- [ ] DevTools → iPhone 12
- [ ] Меню → бургер
- [ ] Карта `/worlds` скроллится
- [ ] Кастомный курсор скрыт

### TC-RESP-02 Tablet — 🟢 P2
- [ ] iPad: layout адаптивный

### TC-RESP-03 Chrome / Safari / Firefox — 🟢 P2
- [ ] Везде одинаковая логика

### TC-RESP-04 Тёмная / светлая тема — 🟡 P1
- [ ] Toggle в шапке: цвета меняются (CSS vars)
- [ ] localStorage сохраняет выбор

---

## ⚡ Модуль 14: Производительность

### TC-PERF-01 First Load — 🟢 P2
- [ ] DevTools → Network → Disable cache → reload `/`
- [ ] Загрузка < 3 сек, TTI < 4 сек

### TC-PERF-02 Размер бандла — 🟢 P2
```bash
docker compose exec frontend du -sh /app/.next/
# Ожидается: < 200MB
```

### TC-PERF-03 GSAP анимации не лагают — 🟡 P1
- [ ] `/worlds`, прокрути карту: 60 FPS (DevTools Performance)

---

## 📊 Матрица приоритетов

| Приоритет | Кол-во | Критерий |
|---|---|---|
| 🔴 P0 — критично для демо | ~25 | Регистрация, логин, профиль, миссии, runner, безопасность |
| 🟡 P1 — важно | ~25 | UI/UX полировка, edge cases, i18n, инвентарь |
| 🟢 P2 — nice-to-have | ~15 | Mobile, performance, темы |

**Минимум перед демо:** все P0 (~25 кейсов, 1.5–2 часа).

---

## 🗂️ Шаблон записи бага

```
ID: BUG-001
TC: TC-MISS-04 (Code-задание базовое)
Серьёзность: P0/P1/P2
Окружение: Chrome 130 / macOS 14 / localhost:3000

Шаги для воспроизведения:
1. ...
2. ...

Ожидаемо: ...
Фактически: ...

Скриншот: [приложить]
Console: [скопировать ошибку]
Network: [статус, URL]
```

---

## 🎯 Как начать прогон

1. Открой 2 окна Chrome side-by-side: левое — приложение, правое — DevTools (Console + Network)
2. Открой 3-й терминал для `docker compose logs backend | grep verify-email`
3. Открой 4-й терминал для Django shell
4. Создай файл `MY_TEST_REPORT.md` рядом с проектом — туда отмечай результаты
5. Иди по чек-листу сверху вниз, отмечай `[x]` галочками
6. Любой провал → копи в шаблон бага → внеси в задачник
