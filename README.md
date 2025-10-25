# RPG Learning Platform (Django + Next.js)

Проект: обучающая RPG-платформа (аналог CodeCombat), цель — вырастить пользователя до Junior Django Developer.

Стек:
- Backend: Django + Django REST Framework, JWT, PostgreSQL, Celery + Redis
- Frontend: Next.js (React) + Tailwind CSS
- Payments: Stripe
- DevOps: Docker, docker-compose, GitHub Actions, Render/Railway/AWS для деплоя

Структура репозитория:
- /backend — Django проект
- /frontend — Next.js приложение
- docker-compose.yml — локальный стек: db, redis, backend, frontend, celery
- .github/workflows — CI

Дальнейшие шаги см. TODOs в .github/ or project board

Manual testing (локально)
------------------------

Ниже шаги для ручного тестирования API и проверки состояния БД/Redis через Docker Compose (macOS, zsh).

1) Поднять сервисы

```bash
# поднять все сервисы (db, redis, backend, frontend, celery)
docker compose up -d

# или поднять только db и redis если backend не нужен
docker compose up -d db redis
```

2) Проверить статус контейнеров

```bash
docker compose ps
```

3) Создать суперпользователя (Django admin)

```bash
docker compose exec backend python manage.py createsuperuser
# или non-interactive (пример):
docker compose exec backend python manage.py createsuperuser --noinput --username admin --email admin@example.com || true
docker compose exec backend python manage.py shell -c "from django.contrib.auth import get_user_model; u=get_user_model().objects.get(username='admin'); u.set_password('adminpass'); u.save()"
```

Admin: http://localhost:8000/admin (логин: admin / пароль: adminpass)

4) Примеры API-запросов (Postman / curl)

- Регистрация (POST)
	- URL: http://localhost:8000/api/auth/register/
	- Body (JSON):
		{
			"username": "test1",
			"password": "pass123",
			"email": "test1@example.com"
		}

- Логин (POST)
	- URL: http://localhost:8000/api/auth/login/
	- Body (JSON):
		{
			"username": "test1",
			"password": "pass123"
		}
	- Ответ: access + refresh токены

- Получить профиль (GET)
	- URL: http://localhost:8000/api/auth/me/
	- Header: Authorization: Bearer <access_token>

5) Проверить данные в Postgres

```bash
# зайти в psql внутри контейнера
docker compose exec db psql -U rpguser -d rpgdb
# или выполнить SQL команду напрямую
docker compose exec db psql -U rpguser -d rpgdb -c "SELECT id, username, email FROM users_user;"
docker compose exec db psql -U rpguser -d rpgdb -c "SELECT id, user_id, xp, level FROM users_profile;"
```

6) Проверить Redis

```bash
docker compose exec redis redis-cli
# в интерактивной консоли: KEYS *
```

7) Статические файлы (если админ без стилей)

```bash
# собрать статику внутри контейнера (если не собрана автоматически)
docker compose exec backend python manage.py collectstatic --noinput
# при необходимости пересоберите образ:
docker compose build backend
docker compose up -d backend
```

8) Логи для отладки

```bash
docker compose logs -f backend
docker compose logs -f celery
```

9) Экспорт/дамп базы

```bash
docker compose exec db pg_dump -U rpguser rpgdb > db-dump.sql
```

Если хотите, могу сгенерировать пример Postman коллекции (JSON) или добавить конкретные curl-примеры для каждого endpoint. 

## Branch Protection

Для обеспечения стабильности и безопасности кода, рекомендуется настроить защиту веток в вашем репозитории. Это поможет предотвратить случайные изменения в основной ветке и обеспечит, что все изменения проходят через процесс проверки.

### Настройка защиты веток

1. Перейдите в настройки вашего репозитория на GitHub.
2. Выберите вкладку "Branches".
3. В разделе "Branch protection rules" нажмите "Add rule".
4. Укажите имя ветки, которую хотите защитить (например, `main`).
5. Установите необходимые параметры защиты, такие как:
	- Требовать проверки статуса перед слиянием
	- Требовать, чтобы все проверки прошли
	- Запретить слияние, если есть конфликты
6. Нажмите "Create" для сохранения правил защиты ветки.
