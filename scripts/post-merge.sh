#!/bin/bash
# Post-merge hook: pushes the current branch to GitHub after a task is merged.
# Idempotent: if the remote is already up to date, the push is a no-op.
# Non-interactive: pulls a fresh OAuth token from the Replit GitHub connector.
set -e

REMOTE_URL="https://github.com/harleypig/pigify.git"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "[post-merge] Branch: ${BRANCH}"
echo "[post-merge] Fetching GitHub token from connector..."
TOKEN="$(node /home/runner/workspace/scripts/get-github-token.mjs)"
if [ -z "${TOKEN}" ]; then
  echo "[post-merge] ERROR: Empty token returned" >&2
  exit 1
fi

echo "[post-merge] Pushing ${BRANCH} to GitHub..."
# Use a one-shot URL with the token; never write it to git config.
git push "https://oauth2:${TOKEN}@github.com/harleypig/pigify.git" "${BRANCH}:${BRANCH}"

echo "[post-merge] Push complete."
