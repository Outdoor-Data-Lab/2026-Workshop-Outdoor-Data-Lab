# syntax=docker/dockerfile:1

# ---------- Dependencies ----------
FROM node:26-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    if [ -f package-lock.json ]; then npm ci; else npm install; fi

# ---------- Development stage ----------
# Vite dev server with HMR; sources are synced/mounted by Compose.
FROM deps AS development
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# ---------- Build stage ----------
FROM deps AS build
COPY . .
RUN npm run build-only

# ---------- Production stage ----------
# Must stay LAST: it is the default target when no --target is given.
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
# SPA fallback so vue-router history mode works on refresh.
# .mjs (MapLibre worker) is missing from nginx's mime.types: browsers refuse a
# module script served as application/octet-stream.
RUN printf 'server {\n  listen 80;\n  root /usr/share/nginx/html;\n  location ~ \\.mjs$ { default_type application/javascript; }\n  location / { try_files $uri $uri/ /index.html; }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
