FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_VERSION=2.4.1

# Install Poetry. (Base-image CVEs are tracked via dependabot's docker
# updates + deliberate base bumps, not a non-deterministic blanket upgrade.)
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

# Layer 1: runtime dependencies only (cached unless the lockfile changes).
# --no-root: the `app` package itself is run from source via PYTHONPATH so
# that Alembic's migrations path (resolved relative to app/db/bootstrap.py)
# points at /app/migrations rather than a site-packages copy.
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --only main --no-root

# Layer 2: application + Alembic migrations.
COPY app ./app
COPY migrations ./migrations

# Non-root user; /data is the mounted volume for the SQLite databases.
RUN useradd --system --create-home --uid 1001 app \
    && mkdir -p /data \
    && chown -R app:app /app /data
USER app

# Version / build hash, injected by CI (image has no .git).
ARG GIT_HASH=""
ARG APP_VERSION=""
ENV GIT_HASH=$GIT_HASH \
    APP_VERSION=$APP_VERSION \
    DATA_DIR=/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Plain HTTP on the internal network; TLS terminates at the frontend nginx.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
