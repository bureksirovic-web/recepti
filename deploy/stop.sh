#!/bin/bash
# =============================================================================
# Recepti — stop tunnel and service
# Run this ON the production server.
# =============================================================================
set -euo pipefail

RECEPTI_DIR="/home/tomi/Recepti"

echo "==> Stopping Cloudflare Tunnel..."
if [ -f "${RECEPTI_DIR}/data/tunnel.pid" ]; then
    kill "$(cat "${RECEPTI_DIR}/data/tunnel.pid")" 2>/dev/null || true
    rm "${RECEPTI_DIR}/data/tunnel.pid"
fi
pkill -f "cloudflared.*recepti" 2>/dev/null || true

echo "==> Stopping Recepti web service..."
sudo systemctl stop recepti-web

echo "=== Recepti stopped ==="