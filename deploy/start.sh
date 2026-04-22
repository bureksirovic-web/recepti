#!/bin/bash
set -euo pipefail

RECEPTI_DIR="/home/tomi/hermes-coder-workspace/repos/Recepti"
CFGD="/home/tomi/.cloudflared/config.yml"
PIDFILE="/tmp/recepti-gunicorn.pid"
LOGFILE="/tmp/recepti-gunicorn.log"

echo "[recepti-web] Stopping old cloudflared tunnel (PID via ps)..."
ps aux | grep 'cloudflared tunnel --url http://localhost:8080 run hahai' | grep -v grep | awk '{print $2}' | xargs -r kill 2>/dev/null || true
sleep 2

echo "[recepti-web] Stopping existing gunicorn..."
if [ -f "$PIDFILE" ]; then
    kill $(cat "$PIDFILE") 2>/dev/null || true
fi
ps aux | grep 'gunicorn.*wsgi:app' | grep -v grep | awk '{print $2}' | xargs -r kill 2>/dev/null || true
sleep 2

echo "[recepti-web] Starting gunicorn..."
cd "$RECEPTI_DIR"
RECEPTI_DATA_DIR=data .venv/bin/gunicorn \
    --bind 127.0.0.1:5001 \
    --workers 2 \
    --timeout 30 \
    --daemon \
    --pid "$PIDFILE" \
    --log-file "$LOGFILE" \
    wsgi:app
sleep 2

if ! ss -tlnp | grep -q 5001; then
    echo "[recepti-web] ERROR: Flask not listening on :5001"
    cat "$LOGFILE"
    exit 1
fi
echo "[recepti-web] Flask running on :5001"

echo "[recepti-web] Starting cloudflared tunnel (ingress rules from config)..."
cd /home/tomi/.cloudflared
nohup /usr/local/bin/cloudflared tunnel --config "$CFGD" run hahai > /tmp/cloudflared-tunnel.log 2>&1 &
CF_PID=$!
echo "[recepti-web] cloudflared PID: $CF_PID"
sleep 5

if ! ps -p $CF_PID > /dev/null 2>&1; then
    echo "[recepti-web] ERROR: cloudflared failed"
    cat /tmp/cloudflared-tunnel.log
    exit 1
fi

echo ""
echo "=== Deployment complete ==="
echo "Recepti web live at: https://recepti.opghaha.eu"
echo "Check tunnel logs: tail -f /tmp/cloudflared-tunnel.log"
echo "Check gunicorn PID: $(cat $PIDFILE)"