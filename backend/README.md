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
