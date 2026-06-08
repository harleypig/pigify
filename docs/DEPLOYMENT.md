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

**pigify is not meant to be public.** How you gate access is up to you —
two complementary models:

- **Built-in authentication** *(planned — not yet implemented).* A future
  mode where pigify gates app access itself, so it can run standalone
  without an external auth layer. Tracked in `TODO.md`.

- **An external forward-auth / SSO proxy.** Put pigify behind whatever you
  already use — **Authelia, Authentik, oauth2-proxy, Cloudflare Access,
  Pomerium, …** — and let it require login before requests reach the app.
  This is the recommended approach today. With Traefik, for example, that
  means attaching your forward-auth middleware to the pigify router; the
  equivalents exist for other proxies.

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
