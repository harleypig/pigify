# Stage 1: build the SPA
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Version / build hash injected by CI; the build has no .git, and the
# changelog generator + vite.config.ts both fall back gracefully.
ARG GIT_HASH=""
ARG APP_VERSION=""
ENV GIT_HASH=$GIT_HASH \
    APP_VERSION=$APP_VERSION
RUN npm run build

# Stage 2: serve the built SPA over HTTPS (TLS terminates here).
FROM nginxinc/nginx-unprivileged:1.31-alpine
# Patch base-image CVEs.
USER root
RUN apk upgrade --no-cache
USER 101
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
# HTTPS; mkcert certs are mounted at /certs by docker-compose.
EXPOSE 8080
