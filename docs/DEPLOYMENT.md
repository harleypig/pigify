# Deployment

pigify is deliberately **deployment- and auth-agnostic** — download it and
fit it into whatever setup you run. There are two moving parts to decide:
how TLS is terminated, and how access to the app is controlled.

## TLS / how it's served

pigify ships as two containers (see `docs/ARCHITECTURE.md`): a FastAPI
backend (plain HTTP, internal) and an nginx frontend that serves the SPA
and proxies `/api` to the backend. Spotify OAuth requires HTTPS, so TLS has
to terminate *somewhere*. Two options:

1. **Standalone (the frontend terminates TLS).** The default image config
   (`frontend/nginx.conf`) serves HTTPS on 8080 using mounted certs. This
   is what `docker compose up` does locally (with mkcert certs from
   `scripts/setup-ssl.sh`); it also works in production with real certs.

2. **Behind a reverse proxy (the proxy terminates TLS).** If you already
   run a TLS-terminating proxy (Traefik, Caddy, nginx, an ingress
   controller, …), let it own public TLS and have the frontend container
   serve plain HTTP. Mount the provided plain-HTTP config over the image's
   default:

   ```yaml
   # compose override for the frontend service
   services:
     frontend:
       volumes:
         - ./deploy/reverse-proxy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
       # no cert mount needed; the proxy terminates TLS in front of :8080
   ```

   Point your proxy at the frontend container's port 8080 and route the
   public hostname to it.

In both cases the backend stays internal; the frontend reaches it as
`http://backend:8000` on the compose network.

## Access control (authentication)

**pigify is not meant to be public, and defaults to locked.** The built-in
access gate is **ON by default and fail-closed**, so a fresh install denies
everyone until you say otherwise — it is never accidentally wide open. Two
models, the first being the default:

- **Built-in access gate (default).** pigify gates access itself, no
  external auth layer needed. It ships enabled (`BUILTIN_AUTH_ENABLED=true`);
  add the permitted Spotify account IDs to `ALLOWED_SPOTIFY_IDS`
  (comma-separated). After Spotify login only those accounts get a session;
  everyone else is redirected back to the login screen. **Fail-closed:** an
  empty allowlist denies everyone — so out of the box **nobody can log in
  until you add your own id**. A denied login is logged with its Spotify ID,
  so the easy path is: try to log in once, copy your ID from the backend
  logs into `ALLOWED_SPOTIFY_IDS`, restart. (A Spotify app in Development
  Mode is *also* capped at the 25 users you add in the Spotify dashboard — a
  coarser allowlist on top of this one.)

- **An external forward-auth / SSO proxy.** If you already run **Authelia,
  Authentik, oauth2-proxy, Cloudflare Access, Pomerium, …**, let it require
  login before requests reach the app and set `BUILTIN_AUTH_ENABLED=false`
  to delegate gating to it. With Traefik, for example, attach your
  forward-auth middleware to the pigify router; the equivalents exist for
  other proxies.

> Note: the app's **Spotify OAuth is not your access-control layer.** It
> authorizes the *Spotify API* for the signed-in user — it does not decide
> who may reach the app. Gate the app with one of the models above.

The Spotify OAuth callback (`/api/auth/spotify/callback`) is hit by the
already-authenticated browser (it carries your auth proxy's session
cookie), so it passes the auth layer without any path whitelist.

## Configuration

Set the runtime config via env / Docker secrets (see `.env.example` and
`docker-compose.yml`):

- `SPOTIFY_REDIRECT_URI` / `FRONTEND_URL` must match your public origin.
- `SPOTIFY_CLIENT_SECRET` + `SECRET_KEY` via files (Docker secrets).
- `ENVIRONMENT=production` refuses the built-in dev `SECRET_KEY`.

## Images

CI publishes `ghcr.io/<owner>/pigify-backend` and `-frontend` on `v*` tags.
Authenticate to pull private packages
(`docker login ghcr.io`), then reference those images in your own compose /
orchestration files instead of building locally.
