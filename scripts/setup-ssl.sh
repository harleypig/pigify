#!/bin/bash
# Setup script for local SSL certificates using mkcert
# This script helps set up HTTPS for local development

set -e

echo "Setting up SSL certificates for local development..."

# Check if mkcert is installed
if ! command -v mkcert &> /dev/null; then
    cat <<EOF
mkcert is not installed.

Install mkcert:
  Ubuntu/Debian:
    sudo apt update
    sudo apt install mkcert

  macOS:
    brew install mkcert

  Windows (with Chocolatey):
    choco install mkcert
EOF
    exit 1
fi

# Install local CA if not already installed
if [ ! -d "$(mkcert -CAROOT)" ]; then
    echo "Installing local Certificate Authority..."
    mkcert -install
fi

# Create certs directory
mkdir -p certs

# Generate certificates for localhost
echo "Generating SSL certificates for localhost..."
mkcert -cert-file certs/localhost+2.pem -key-file certs/localhost+2-key.pem localhost 127.0.0.1 ::1

echo ""
echo "✓ SSL certificates generated successfully!"
echo ""
echo "Certificates are in the certs/ directory:"
echo "  - certs/localhost+2.pem (certificate)"
echo "  - certs/localhost+2-key.pem (private key)"
echo ""
echo "The docker-compose.yml will automatically use these certificates."
echo "Access your app at https://localhost:8000"

