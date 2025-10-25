FROM node:20-alpine
WORKDIR /app
# copy package files (works with or without package-lock.json)
COPY package*.json ./
# install dependencies: prefer npm ci when lockfile present, fallback to npm install
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY . .
RUN npm run build
CMD ["npm","start"]
