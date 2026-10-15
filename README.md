<p align="center">
  <img src="static/logo.png" alt="KMtracker" width="320">
</p>

# KMtracker

Self-hosted vehicle tracker: mileage, fuel, expenses and maintenance for
multiple cars and motorbikes. Web app (Flask + SQLite) plus an optional
Telegram bot, in a single Docker image.

[Leer en español](README.es.md)

## Features

- **Multiple vehicles** (cars and motorbikes, ES/PT plates), including sold/test
  vehicles and partial or total odometer modes.
- **Mileage log**: partial (trip) or total (odometer) readings, corrections.
- **Fuel**: fill-ups, L/100 km consumption, price history, odometer correction.
- **Expenses**: categories (insurance, MOT/ITV, tax, repair, cleaning,
  maintenance, improvements, other) with invoice photos.
- **Maintenance**: km-based items with alerts, service records, printable
  thermal tickets (58 mm) and per-vehicle PDF reports.
- **Dashboard and reports**: monthly/monthly-per-car stats, daily report
  (Excel-style), CSV export, Chart.js charts.
- **Documents** per vehicle stored in the database.
- **Local rotating backups** from the admin panel (no external service needed).
- **Optional Telegram bot** with a user allowlist.
- Single-password web login, CSRF protection and login rate limiting.

## Quick start (Docker)

```bash
git clone https://github.com/Robertomola18/kmtracker.git && cd kmtracker
cp .env.example .env          # set KMTRACKER_PASSWORD
docker compose up -d --build
```

Open `http://localhost:5050` and log in with `KMTRACKER_PASSWORD`.

Data lives in the `kmtracker_data` volume (`/data`). To load demo data:

```bash
docker compose exec kmtracker python3 /app/seed.py
```

> Recommended: put KMtracker behind a TLS reverse proxy (Caddy, nginx, Traefik)
> or a VPN such as Tailscale/WireGuard, and only expose port 5050 on the LAN.

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `KMTRACKER_PASSWORD` | — | Web login password. Required on first run. |
| `KMTRACKER_DB_PATH` | `/data/kmtracker.db` | SQLite database path. |
| `KMTRACKER_SECRET_KEY` | generated in `/data/.secret_key` | Flask session secret. |
| `TZ` | `Europe/Madrid` | Time zone. |
| `KM_BACKUP_DIR` | `<db dir>/backups` | Local backup directory. |
| `KM_BACKUP_KEEP_COUNT` | `10` | Backups kept regardless of age. |
| `KM_BACKUP_KEEP_DAYS` | `30` | Older backups are pruned. |
| `TELEGRAM_TOKEN` | — | Bot token (or set it in `/admin`). |
| `TELEGRAM_ALLOWED_USER_IDS` | — | Comma-separated Telegram user IDs (recommended). |

## Telegram bot (optional)

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Put the token and your numeric Telegram user ID in `.env`:
   `TELEGRAM_TOKEN=123:ABC` and `TELEGRAM_ALLOWED_USER_IDS=111111111`.
3. Start it:

```bash
docker compose --profile bot up -d
```

The bot can also be configured from the web at `/admin` (settings are stored in
the database). **Always set an allowlist**: without it, anyone who finds the bot
can read and modify your data.

## Backups

`/admin` lets you create, list, download, restore and delete local backups
(`kmtracker_<timestamp>.tar.gz` containing the SQLite database). You can also
download/upload the raw `.db` file. Point `KM_BACKUP_DIR` at a mounted NAS or an
external/Synced folder to keep off-site copies. An example cron job:

```
0 5 * * * docker compose -f /path/kmtracker/docker-compose.yml exec -T kmtracker \
  python3 -c "import backup,os;backup.create_backup(os.environ['KMTRACKER_DB_PATH'])"
```

## Development and tests

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
KMTRACKER_DB_PATH=/tmp/km.db KMTRACKER_PASSWORD=dev pytest -q
```

## Tech stack

Flask · SQLite (WAL) · Jinja2 · Chart.js · WeasyPrint (PDF) ·
python-telegram-bot · gunicorn · Docker.

## License

Licensed under the **GNU AGPL-3.0**. See [LICENSE](LICENSE).

Created by Rober Da Silva (DjGuesh) · Rsilva Corp Limited.
