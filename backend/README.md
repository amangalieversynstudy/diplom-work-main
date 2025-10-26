Backend: Django app

Run locally (recommended using docker-compose):

1. Copy .env.example to .env and edit DB/SECRET
2. docker-compose up --build

API endpoints:
- /api/users/
- /api/locations/
- /api/missions/
- /api/progress/

Celery: celery -A core worker -l info

## Game API

- Locations `/api/locations/` (GET list, GET detail)
	- Nested missions are included on detail
	- Mission fields include: `id, title, description, xp_reward, order, is_active, min_level, repeatable, repeat_xp_rate, pos_x, pos_y, available, user_progress`
	- Availability respects `min_level`, `is_active`, and `prerequisites`
- Missions `/api/missions/{id}/` (GET)
	- actions:
		- `POST /api/missions/{id}/start/`
		- `POST /api/missions/{id}/complete/` (optional body: `{ "stars": 0..3 }`)
