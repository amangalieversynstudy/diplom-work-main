Frontend: Next.js + Tailwind

Run locally

1. Install deps and start dev server

- cd frontend
- npm install --no-audit --no-fund
- npm run dev

If port 3000 is busy:

- npm run dev -- -p 3002 -H 127.0.0.1
- Open http://127.0.0.1:3002

2. Backend API base URL

- Default: frontend uses built-in mock API under Next.js pages/api (no backend required)
- To use real DRF backend, create .env.local with:
  NEXT_PUBLIC_API_BASE=http://localhost:8000/api

Auth pages

- Login: http://localhost:3000/login (или на порту, где запущено)
- Register: http://localhost:3000/register
- После регистрации перейдите на Login и войдите. Для DRF-логина используйте username + password.

3. Backend requirements (Django/DRF)

- Only needed if NEXT_PUBLIC_API_BASE points to Django:
  - CORS must allow the frontend origin (e.g. http://localhost:3000, http://127.0.0.1:3002)
  - JWT endpoints expected: - POST /api/auth/jwt/create/ - POST /api/auth/jwt/refresh/ - Missions/Profile endpoints used in the app

Troubleshooting

- Husky prepare in non-git: handled in package.json, install should not fail
- Tailwind/PostCSS: postcss.config.js requires autoprefixer (already in deps)
- Port conflicts: free the port or use -p 3002
