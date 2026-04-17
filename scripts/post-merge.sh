#!/bin/bash
# Post-merge hook: pushes the current branch to GitHub after a task is merged.
# Idempotent: if the remote is already up to date, the push is a no-op.
# Non-interactive: uses GITHUB_PUSH_TOKEN secret for auth.
set -e

if [ -z "${GITHUB_PUSH_TOKEN}" ]; then
  echo "[post-merge] GITHUB_PUSH_TOKEN is not set; skipping push." >&2
  exit 0
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "[post-merge] Pushing ${BRANCH} to GitHub..."

# One-shot URL with the token; never written to git config.
git push "https://x-access-token:${GITHUB_PUSH_TOKEN}@github.com/harleypig/pigify.git" "${BRANCH}:${BRANCH}"

echo "[post-merge] Push complete."
