# KMtracker

Gestor de vehículos autoalojado: kilometraje, combustible, gastos y
mantenimiento para varios coches y motos. App web (Flask + SQLite) más un bot de
Telegram opcional, en una sola imagen Docker.

[Read in English](README.md)

## Características

- **Varios vehículos** (coches y motos, matrículas ES/PT), incluyendo vehículos
  vendidos o de prueba y modos de cuentakilómetros parcial o total.
- **Kilometraje**: lecturas parciales (viaje) o totales (odómetro), correcciones.
- **Combustible**: repostajes, consumo L/100 km, histórico de precios, corrección
  del odómetro.
- **Gastos**: categorías (seguro, ITV, impuesto, reparación, limpieza,
  mantenimiento, mejoras, otro) con fotos de factura.
- **Mantenimiento**: items por km con alertas, registros de servicio, tickets
  imprimibles (58 mm) y PDF por vehículo.
- **Panel e informes**: estadísticas mensuales/por coche, informe diario estilo
  Excel, exportación CSV, gráficas con Chart.js.
- **Documentos** por vehículo guardados en la base de datos.
- **Copias de seguridad locales rotativas** desde el panel de administración
  (sin depender de ningún servicio externo).
- **Bot de Telegram opcional** con lista blanca de usuarios.
- Login web con contraseña única, protección CSRF y límite de intentos.

## Arranque rápido (Docker)

```bash
git clone <repo-url> kmtracker && cd kmtracker
cp .env.example .env          # define KMTRACKER_PASSWORD
docker compose up -d --build
```

Abre `http://localhost:5050` y entra con `KMTRACKER_PASSWORD`.

Los datos viven en el volumen `kmtracker_data` (`/data`). Para cargar datos de
ejemplo:

```bash
docker compose exec kmtracker python3 /app/seed.py
```

> Recomendado: pon KMtracker detrás de un proxy inverso con TLS (Caddy, nginx,
> Traefik) o una VPN tipo Tailscale/WireGuard, y expón el puerto 5050 solo en tu
> red local.

## Configuración (variables de entorno)

| Variable | Por defecto | Descripción |
|---|---|---|
| `KMTRACKER_PASSWORD` | — | Contraseña del acceso web. Obligatoria la primera vez. |
| `KMTRACKER_DB_PATH` | `/data/kmtracker.db` | Ruta de la base de datos SQLite. |
| `KMTRACKER_SECRET_KEY` | generada en `/data/.secret_key` | Clave de sesión de Flask. |
| `TZ` | `Europe/Madrid` | Zona horaria. |
| `KM_BACKUP_DIR` | `<carpeta BD>/backups` | Carpeta de copias de seguridad. |
| `KM_BACKUP_KEEP_COUNT` | `10` | Copias conservadas sin importar la antigüedad. |
| `KM_BACKUP_KEEP_DAYS` | `30` | Las copias más antiguas se purgan. |
| `TELEGRAM_TOKEN` | — | Token del bot (o configúralo en `/admin`). |
| `TELEGRAM_ALLOWED_USER_IDS` | — | IDs de Telegram autorizados, separados por comas (recomendado). |

## Bot de Telegram (opcional)

1. Crea un bot con [@BotFather](https://t.me/BotFather) y copia el token.
2. Pon el token y tu ID numérico de Telegram en `.env`:
   `TELEGRAM_TOKEN=123:ABC` y `TELEGRAM_ALLOWED_USER_IDS=111111111`.
3. Arrástralo con:

```bash
docker compose --profile bot up -d
```

También se puede configurar desde la web en `/admin` (los ajustes se guardan en
la base de datos). **Configura siempre la lista blanca**: sin ella, cualquiera
que encuentre el bot puede leer y modificar tus datos.

## Copias de seguridad

En `/admin` puedes crear, listar, descargar, restaurar y borrar copias locales
(`kmtracker_<fecha>.tar.gz` con la base de datos SQLite). También puedes
descargar/subir el fichero `.db` directamente. Apunta `KM_BACKUP_DIR` a un NAS
montado o a una carpeta sincronizada para tener copias fuera del servidor.
Ejemplo de cron:

```
0 5 * * * docker compose -f /ruta/kmtracker/docker-compose.yml exec -T kmtracker \
  python3 -c "import backup,os;backup.create_backup(os.environ['KMTRACKER_DB_PATH'])"
```

## Desarrollo y tests

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
KMTRACKER_DB_PATH=/tmp/km.db KMTRACKER_PASSWORD=dev pytest -q
```

## Tecnologías

Flask · SQLite (WAL) · Jinja2 · Chart.js · WeasyPrint (PDF) ·
python-telegram-bot · gunicorn · Docker.

## Licencia

Bajo **GNU AGPL-3.0**. Ver [LICENSE](LICENSE).

Creado por Rober Da Silva (DjGuesh) · Rsilva Corp Limited.
