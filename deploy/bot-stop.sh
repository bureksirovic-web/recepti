#!/bin/bash
# =============================================================================
# Recepti — stop the durable Telegram bot (systemd)
# Run ON the production server (host).
# =============================================================================
set -euo pipefail

SERVICE="recepti-bot.service"

echo "==> Stopping $SERVICE..."
sudo systemctl stop "$SERVICE" 2>/dev/null || true
sudo systemctl disable "$SERVICE" 2>/dev/null || true
sudo systemctl daemon-reload

echo "=== Bot stopped (service disabled; rerun deploy/bot-start.sh to re-enable) ==="
