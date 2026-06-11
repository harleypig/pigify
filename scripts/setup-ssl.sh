#!/usr/bin/env bash
# Generate local HTTPS certificates with mkcert. Spotify OAuth requires
# HTTPS, and in the docker-compose stack TLS terminates at the frontend
# nginx, which mounts these certs from docker/certs.
#
# WSL note: run this *inside* your WSL distro (not the Windows host).
# Install the Linux mkcert binary + libnss3-tools there; generating the
# certs in-distro avoids the host/WSL trust-store issues that make mkcert
# flaky from Windows.

set -euo pipefail

# Resolve repo root from this script's location so it works from anywhere.
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "$script_dir/.." && pwd)

cd "$repo_root"

echo "Setting up SSL certificates for local development..."

if ! command -v mkcert &> /dev/null; then
  cat <<'EOF' >&2
mkcert is not installed.

Install mkcert (and libnss3-tools, which mkcert needs for -install):
  Ubuntu/Debian/WSL:
    sudo apt update
    sudo apt install -y libnss3-tools mkcert

  macOS:
    brew install mkcert nss

  Windows (with Chocolatey):
    choco install mkcert
EOF
  exit 1
fi

# Install the local CA if it isn't already trusted.
if [[ ! -d $(mkcert -CAROOT) ]]; then
  echo "Installing local Certificate Authority..."
  mkcert -install
fi

mkdir -p docker/certs

echo "Generating SSL certificates for local development..."
mkcert \
  -cert-file docker/certs/dev-cert.pem \
  -key-file docker/certs/dev-key.pem \
  127.0.0.1 ::1

# The nginx-unprivileged container runs as uid 101 and must read the key
# through the read-only bind mount. mkcert writes the key 0600 by default,
# which that uid can't read. These are throwaway local-dev certs, so make
# the key world-readable. Do NOT do this for production keys.
chmod 644 docker/certs/dev-key.pem

cat <<'EOF'

✓ SSL certificates generated successfully!

Certificates are in the docker/certs/ directory:
  - docker/certs/dev-cert.pem      (certificate)
  - docker/certs/dev-key.pem  (private key)

docker/docker-compose.yml mounts these into the frontend container
automatically. Start the stack with:  docker compose up --build
Then open:             https://127.0.0.1:8080

Set your Spotify app's redirect URI to:
  https://127.0.0.1:8080/api/auth/spotify/callback
EOF
