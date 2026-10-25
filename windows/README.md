# KMtracker on Windows 10/11

KMtracker runs on Windows through **Docker Desktop with Linux containers**. You
do not need to install Python, Pango, Cairo or WeasyPrint on Windows: everything
runs inside the application image.

This is the supported Windows setup. There is no native `.exe` version yet.

- [Requirements](#requirements)
- [1. Install Docker Desktop](#1-install-docker-desktop)
- [2. Get the code](#2-get-the-code)
- [3. Configure `.env`](#3-configure-env)
- [4. Start KMtracker](#4-start-kmtracker)
- [5. Stop, start and update](#5-stop-start-and-update)
- [6. Backups](#6-backups)
- [7. Telegram bot (optional)](#7-telegram-bot-optional)
- [8. Access from other devices](#8-access-from-other-devices)
- [9. Data and volumes](#9-data-and-volumes)
- [10. Troubleshooting](#10-troubleshooting)
- [11. Uninstall](#11-uninstall)

## Requirements

- Windows 10/11, 64-bit (Home or Pro) with current updates.
- Hardware virtualization enabled in the BIOS/UEFI.
- Administrator rights to install Docker Desktop and WSL2.
- **Docker Desktop** with the WSL2 backend, running **Linux containers**.
- Internet access for the first image build.
- Git for Windows, or the repository downloaded as a ZIP.

Docker Desktop is free for personal use. It includes Docker Compose v2, so use
`docker compose` (with a space), not the old `docker-compose` command.

## 1. Install Docker Desktop

1. Install Docker Desktop from the official site:
   <https://www.docker.com/products/docker-desktop/>
2. During setup, keep the **WSL 2** backend enabled. If WSL2 is not installed,
   run the following in an Administrator PowerShell, then reboot:

   ```powershell
   wsl --install
   ```

3. Start Docker Desktop and wait until it says the engine is running.
4. Make sure Docker Desktop is using **Linux containers**. If the tray menu
   offers “Switch to Linux containers”, use that option.
5. Open a new PowerShell window and verify:

   ```powershell
   docker version
   docker compose version
   docker info --format '{{.OSType}}'
   ```

   The last command must print `linux`. If it prints `windows`, switch Docker
   Desktop back to Linux containers.

If `docker` is not recognized, close and reopen PowerShell. If it still fails,
repair or reinstall Docker Desktop.

## 2. Get the code

```powershell
git clone https://github.com/Robertomola18/kmtracker.git
cd kmtracker
```

If you do not have Git, download the ZIP from GitHub, extract it, and open a
PowerShell window inside the extracted folder. All commands below must be run
from the folder that contains `docker-compose.yml`.

The repository includes a `.gitattributes` file that keeps `entrypoint.sh` in LF
format, so a normal Windows clone works correctly.

## 3. Configure `.env`

Create your local configuration file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set a strong value for `KMTRACKER_PASSWORD`. Do not leave the example
`cambia-esta-contrasena` value in place. The `.env` file is ignored by Git and
must not be committed.

Recommended settings:

```dotenv
KMTRACKER_PASSWORD='a long and unique password'
TZ=Europe/Madrid
```

Notes:

- Save `.env` as **UTF-8 without BOM**. A BOM can make Docker Compose ignore the
  first variable.
- If the password contains `#`, `$`, double quotes or spaces, wrap it in single
  quotes as shown above. If it contains a single quote, use the PowerShell
  environment variable method below for the first start.
- The password is only used to create the password hash on the **first start**.
  Changing `KMTRACKER_PASSWORD` later does not change the existing password.
- To avoid writing the password to `.env` at all, set it only for the first
  start:

  ```powershell
  $env:KMTRACKER_PASSWORD = "a long and unique password"
  docker compose up -d --build
  Remove-Item Env:\KMTRACKER_PASSWORD
  ```

  The password hash is stored in the database volume after the first start.

## 4. Start KMtracker

From the repository folder:

```powershell
docker compose up -d --build
docker compose ps
```

The first build can take several minutes. Open:

<http://localhost:5050>

Log in with the password you configured. To follow the logs:

```powershell
docker compose logs -f kmtracker
```

If the container is restarting instead of running, see
[Troubleshooting](#10-troubleshooting).

Optional demo data (fake cars, fill-ups and expenses):

```powershell
docker compose exec kmtracker python3 /app/seed.py
```

Do not load demo data into a database that already contains your real data.

## 5. Stop, start and update

Stop the application without deleting data:

```powershell
docker compose stop
```

Start it again:

```powershell
docker compose start
```

Update KMtracker. Back up first, then:

```powershell
git pull --ff-only
docker compose up -d --build
```

The database and uploads live in named volumes, so they survive rebuilds. If
`git pull` reports local changes, commit or stash them before updating. Do not
run `git reset --hard` if you have work you want to keep.

## 6. Backups

The easiest option is the web interface:

1. Open `/admin`.
2. Create a backup and download it.
3. Restore a backup from the same page.

Backups are stored in `/data/backups` inside the `kmtracker_data` volume. To copy
a backup to Windows:

```powershell
docker cp kmtracker:/data/backups/<backup-name>.tar.gz .
```

Keep an exported copy outside Docker. A backup stored only in the same Docker
volume is lost if that volume is deleted.

Do not copy `kmtracker.db` while the application is running; SQLite may be in the
middle of a write. Use `/admin` or the SQLite-safe backup command. For a manual
restore, stop the container first.

## 7. Telegram bot (optional)

Start the web application first, then the bot:

```powershell
docker compose --profile bot up -d
```

Configure the token either in `.env` (`TELEGRAM_TOKEN`) or in `/admin`. Set
`TELEGRAM_ALLOWED_USER_IDS` (or the equivalent `/admin` setting); otherwise
anyone who finds the bot can use it.

If you change the token in `/admin`, restart the bot:

```powershell
docker compose --profile bot restart bot
```

The bot only makes outbound connections to Telegram; do not open an inbound port
for it.

## 8. Access from other devices

By default, `docker-compose.yml` publishes port 5050 on all interfaces. That
means other devices on your network may be able to reach it.

For **this PC only**, edit `docker-compose.yml` and change:

```yaml
ports:
  - "5050:5050"
```

to:

```yaml
ports:
  - "127.0.0.1:5050:5050"
```

To access KMtracker from a phone or tablet on the same Wi-Fi, keep the port
published, allow Docker Desktop on **private networks** in Windows Firewall, and
open `http://<your-pc-ip>:5050`.

For remote access, use a VPN such as Tailscale or WireGuard, or put KMtracker
behind an HTTPS reverse proxy. Do not forward port 5050 on your router and do not
expose it directly to the Internet.

## 9. Data and volumes

KMtracker uses two named volumes:

- `kmtracker_data`: SQLite database, secret key and local backups.
- `kmtracker_uploads`: uploaded files.

Compose prefixes volume names with the project name, which normally comes from
the folder name. If you rename or move the project folder, Docker may create new
empty volumes. Keep the folder name stable, or export a backup before moving it.

Do not replace `/data` with a bind mount to a Windows folder such as `C:\...`.
SQLite and WAL locking are unreliable on NTFS bind mounts. Keep the named
volumes and use the backup/export tools.

- `docker compose down` stops and removes containers but keeps the volumes.
- `docker compose down -v` also deletes the volumes and all KMtracker data.
  This is irreversible.
- Resetting Docker Desktop, uninstalling it, or deleting its WSL2 data can also
  remove volumes. Export backups regularly.

## 10. Troubleshooting

| Problem | Solution |
| --- | --- |
| `docker` is not recognized | Install/start Docker Desktop, then open a new PowerShell window. |
| `Cannot connect to the Docker daemon` | Start Docker Desktop and wait for the engine. Check with `docker info`. |
| `docker info` reports `OSType: windows` | Right-click the Docker Desktop tray icon and switch to Linux containers. |
| `docker compose` is not recognized | Update Docker Desktop. Use `docker compose`, not `docker-compose`. |
| `entrypoint.sh: bad interpreter` or `$'\r'` | The file has Windows CRLF endings. Pull the latest version and run `git checkout -- entrypoint.sh`, then rebuild with `docker compose up -d --build`. The Dockerfile also normalizes the file during the build. |
| `KMTRACKER_PASSWORD no definida` | Set `KMTRACKER_PASSWORD` in `.env`, then run `docker compose up -d --force-recreate`. Check `docker compose logs kmtracker`. |
| The container keeps restarting | Run `docker compose logs kmtracker`. The usual causes are a missing password, a port conflict or a build problem. |
| `port is already allocated` | Find the process with `Get-NetTCPConnection -LocalPort 5050`, or change the host side to `5051:5050` and open `http://localhost:5051`. |
| The container name `kmtracker` is already in use | Run `docker ps -a --filter "name=kmtracker"`. Stop the old instance with `docker compose down` in its folder, or remove the old container. Use only one instance. |
| `git pull` fails because of local changes | Run `git status`. Commit or stash your changes. Do not use `git reset --hard` if you want to keep them. |
| WSL2 errors or Docker Desktop will not start | Run `wsl --update`, then `wsl --shutdown`, and start Docker Desktop again. Check that virtualization is enabled in the BIOS/UEFI. |
| Cannot log in after changing `.env` | The password hash was already created on the first start. Changing the environment variable does not update it. Restore a backup or reset the database password; there is no password-change screen in this version. |
| No space left on device | Free space in Docker Desktop or move its disk image to a larger drive. Do not delete volumes unless you have a backup. |

### Reset a forgotten password

Changing `KMTRACKER_PASSWORD` in `.env` does not update an existing password
hash. If you have forgotten the password, create a backup first, set the new
password in `.env`, then run these commands with the container running:

```powershell
docker compose exec kmtracker python3 -c "from models import get_db; conn = get_db(); conn.execute('DELETE FROM settings WHERE key = ?', ('password_hash',)); conn.commit(); conn.close()"
docker compose up -d --force-recreate
```

The first command deletes the stored hash. The second recreates the container so
the entrypoint creates a new hash from `KMTRACKER_PASSWORD`. This does not delete
your vehicles, expenses or other data.

## 11. Uninstall

Stop the application:

```powershell
docker compose down
```

This keeps your data. To delete the containers **and all data volumes**:

```powershell
docker compose down -v
```

The second command is irreversible. Export a backup first if you may need the
data later.

You can then delete the repository folder and uninstall Docker Desktop if you no
longer need it. Back up the volumes before uninstalling Docker Desktop or
resetting its data.

## Security notes

- Use a long, unique password. The web interface uses a single password.
- Keep port 5050 on localhost or your private LAN whenever possible.
- Do not expose KMtracker directly to the Internet without HTTPS or a VPN.
- Set `TELEGRAM_ALLOWED_USER_IDS` if you use the bot.
- Keep Docker Desktop and the KMtracker image updated.
- Never commit `.env` or backups containing personal data.

## Known limitations

- KMtracker on Windows requires Docker Desktop; there is no native `.exe` yet.
- Docker Desktop must be running before you can use KMtracker.
- This setup does not install a Windows service or start automatically at login.
- The password is created on first start; changing `KMTRACKER_PASSWORD` later does
  not update the existing password.
- The default compose file publishes port 5050 on all interfaces. See
  [Access from other devices](#8-access-from-other-devices) to restrict it.
