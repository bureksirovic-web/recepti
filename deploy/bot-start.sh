#!/bin/bash
# =============================================================================
# Recepti — durable Telegram BOT deployment (systemd)
# Run ON the production server (host). Installs + starts recepti-bot.service.
# The bot polls Telegram indefinitely; survives reboots / container restarts.
#
# Requires (on the host):
#   - /home/tomi/Recepti  (repo clone; or adjust RECEPTI_DIR below)
#   - /home/tomi/Recepti/.venv  (python3 -m pip install -r requirements.txt)
#   - RECEPTI_BOT_TOKEN + OPENROUTER_API_KEY
#
# Secrets: first run writes /home/tomi/Recepti/.env from the current shell
# environment when those vars are already exported; otherwise prompts.
# =============================================================================
set -euo pipefail

RECEPTI_DIR="/home/tomi/Recepti"
SERVICE="recepti-bot.service"
ENV_FILE="${RECEPTI_DIR}/.env"
UNIT_SRC="${RECEPTI_DIR}/deploy/systemd/${SERVICE}"
UNIT_DST="/etc/systemd/system/${SERVICE}"

if [ ! -d "$RECEPTI_DIR" ]; then
    echo "ERROR: $RECEPTI_DIR not found. Clone the repo there (or edit RECEPTI_DIR in this script)." >&2
    exit 1
fi

# --- Ensure the secret env file exists --------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    echo "==> Creating $ENV_FILE (chmod 600) from environment..."
    : > "$ENV_FILE"
    for v in RECEPTI_BOT_TOKEN OPENROUTER_API_KEY; do
        if [ -n "${!v:-}" ]; then
            echo "$v=${!v}" >> "$ENV_FILE"
        else
            read -r -p "  $v (paste value, leave empty to skip): " val
            [ -n "$val" ] && echo "$v=$val" >> "$ENV_FILE"
        fi
    done
    chmod 600 "$ENV_FILE"
else
    echo "==> $ENV_FILE already exists (leaving as-is)."
fi

# --- Install unit ------------------------------------------------------------
echo "==> Installing systemd unit..."
sudo cp "$UNIT_SRC" "$UNIT_DST"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl restart "$SERVICE"

sleep 3
if systemctl is-active --quiet "$SERVICE"; then
    echo ""
    echo "=== Bot deployed ==="
    echo "  live at: @Hahai_recepti_bot  (send /start to activate)"
    echo "  status:  sudo systemctl status recepti-bot"
    echo "  logs:    tail -f ${RECEPTI_DIR}/data/logs/bot.log"
else
    echo "ERROR: $SERVICE failed to start. Checking logs..." >&2
    sudo journalctl -u "$SERVICE" -n 40 --no-pager
    exit 1
fi
