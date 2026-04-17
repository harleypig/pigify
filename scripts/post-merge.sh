#!/bin/bash
# Post-merge hook: installs Python dependencies, then pushes to GitHub.
# Idempotent: safe to run multiple times.
# Non-interactive: no prompts.
set -e

echo "[post-merge] Installing Python dependencies..."
uv pip install -r backend/requirements.txt --quiet
echo "[post-merge] Dependencies installed."

if [ -z "${GITHUB_PUSH_TOKEN}" ]; then
  echo "[post-merge] GITHUB_PUSH_TOKEN is not set; skipping push." >&2
  exit 0
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "[post-merge] Pushing ${BRANCH} to GitHub..."

# One-shot URL with the token; never written to git config.
git push "https://x-access-token:${GITHUB_PUSH_TOKEN}@github.com/harleypig/pigify.git" "${BRANCH}:${BRANCH}"

echo "[post-merge] Push complete."
