# Recepti — Deployment Guide

## What gets deployed

| Component | Port | How it works |
|---|---|---|
| Flask web app | 5001 | Serves static HTML + REST API |
| Cloudflare Tunnel | — | Exposes port 5001 as https://recepti.opghaha.eu |
| Telegram bot | — | Long-running polling; answers in-chat commands |

## Prerequisites

- `cloudflared` installed: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/install-and-setup/installation
- systemd available on the server
- Recepti repo cloned at `/home/tomi/Recepti`
- Python 3.11+ venv at `/home/tomi/Recepti/.venv`

## One-time setup

On the server, clone or sync the Recepti repo:

```bash
git clone https://github.com/YOUR_GITHUB/recepti.git /home/tomi/Recepti
cd /home/tomi/Recepti
pip install -r requirements.txt    # or: pip install -e .
```

Or if already cloned, pull latest:

```bash
cd /home/tomi/Recepti && git pull
```

## Deploy (first time)

```bash
cd /home/tomi/Recepti
chmod +x deploy/start.sh deploy/stop.sh
sudo bash deploy/start.sh
```

## Redeploy (after updates)

```bash
cd /home/tomi/Recepti
git pull
sudo systemctl restart recepti-web
# Tunnel auto-reconnects; no restart needed unless it breaks
```

## Deploy the Telegram bot (durable, always-on)

The web app and tunnel are separate from the bot. To run the bot so it survives
reboots / container restarts, install it as a systemd service:

```bash
cd /home/tomi/Recepti
chmod +x deploy/bot-start.sh deploy/bot-stop.sh
sudo bash deploy/bot-start.sh     # creates .env, installs + starts recepti-bot.service
```

Requirements on the host (checked by `bot-start.sh`):
- Repo at `/home/tomi/Recepti` and a venv at `/home/tomi/Recepti/.venv`
- `RECEPTI_BOT_TOKEN` and `OPENROUTER_API_KEY` set in the shell (first run writes
  them to `/home/tomi/Recepti/.env`, chmod 600 — never committed), or paste them
  when prompted.

Once the service is up, open the bot (@Hahai_recepti_bot) and send **/start** to
activate it, then try `/search`, `/plan`, `/shopping`, `/kuhano`, `/okusi`.

```bash
sudo systemctl status recepti-bot --no-pager   # status
tail -f /home/tomi/Recepti/data/logs/bot.log   # logs
sudo bash deploy/bot-stop.sh                   # stop + disable
```

> The unit (`deploy/systemd/recepti-bot.service`) hardens the process
> (NoNewPrivileges, ReadWritePaths, PrivateTmp) and auto-restarts on failure.

## Stop

```bash
sudo bash /home/tomi/Recepti/deploy/stop.sh
```

## Check status

```bash
sudo systemctl status recepti-web --no-pager
tail -f /home/tomi/Recepti/data/logs/web.log      # Flask output
tail -f /home/tomi/Recepti/data/logs/tunnel.log  # Cloudflare Tunnel
```

## Logs

- App logs: `/home/tomi/Recepti/data/logs/web.log`
- Tunnel logs: `/home/tomi/Recepti/data/logs/tunnel.log`
- Tunnel PID: `/home/tomi/Recepti/data/tunnel.pid`

## Troubleshooting

**Tunnel won't start:**
```bash
cloudflared tunnel --url http://localhost:5001 --loglevel info run recepti
# Run interactively to see the real error
```

**Service won't start:**
```bash
sudo journalctl -u recepti-web -f --no-pager
```

**"502 Bad Gateway" on the web:**
Check that the service and tunnel are both running:
```bash
sudo systemctl status recepti-web
curl http://localhost:5001/   # should return HTML
```

## HTTPS / SSL

Cloudflare Tunnel provides free HTTPS automatically — no certbot or nginx needed.
The tunnel handles SSL termination at the edge.

## Alternative: via nginx (no Cloudflare Tunnel)

If you prefer nginx routing instead of Cloudflare Tunnel, add to your nginx config:

```
server {
    server_name recepti.opghaha.eu;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then get a certificate:
```bash
sudo certbot --nginx -d recepti.opghaha.eu
sudo systemctl reload nginx
```

In this case, skip the Cloudflare Tunnel step in `deploy/start.sh`.