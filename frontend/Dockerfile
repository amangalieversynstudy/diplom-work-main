FROM node:20-bullseye
WORKDIR /app
COPY package*.json ./
# install dependencies for dev (fallback to npm install if no lock)
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
# Copy sources (in dev we will override by volume)
COPY . .
# Default to dev server; docker-compose can override
CMD ["npm","run","dev"]
