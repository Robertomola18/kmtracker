# Changelog

Todas las versiones notables de KMtracker.

## [Sin publicar]

### Seguridad
- Actualizadas dependencias: WeasyPrint 70.0 (Pillow 13), requests 2.34.2,
  Werkzeug 3.1.9, MarkupSafe 3.0.4, click 8.5.0, gunicorn 26.2.0,
  certifi 2026.10.23 y brotli 1.2.1; auditoría OSV sin vulnerabilidades conocidas.
- Imagen base Debian con `apt-get upgrade` y `pip`/`setuptools`/`wheel` al día.

### Añadido
- **Soporte para Windows 10/11** mediante Docker Desktop y WSL2, con guías de
  instalación en `windows/README.es.md` y `windows/README.md`.
- Soporte de categoría de gasto **"Mejoras"** y aceptación de **coma decimal**
  en todos los campos numéricos de los formularios.
- **Copias de seguridad locales rotativas** desde `/admin` (crear, listar,
  descargar, restaurar, borrar), sin depender de servicios externos.
- **Lista blanca** de usuarios para el bot de Telegram
  (`TELEGRAM_ALLOWED_USER_IDS` / ajuste `telegram_allowed_ids`).
- Bot de Telegram empaquetado como **servicio opcional** (`--profile bot`).

### Corregido
- `entrypoint.sh` se normaliza durante la construcción para tolerar finales de
  línea CRLF en clones de Windows.
- `/admin/restore` ya no devuelve 405: muestra una página propia con el
  formulario de subida y un enlace desde `/admin`.
- La raíz `/` redirige al panel o al login en vez de devolver 404.
- El límite de subida de bases de datos se eleva a 128 MB y los archivos
  demasiado grandes muestran un aviso claro en vez de un error 413 genérico.
- Restauración de la base más segura: valida la integridad del archivo, elimina
  los sidecars WAL/SHM antiguos, conserva la base anterior como `.bak` y
  recupera automáticamente esa copia si falla la migración.
- La descarga de la base actual usa la API de backup de SQLite para no entregar
  una copia inconsistente cuando hay datos pendientes en el WAL.
- `mantenimiento` faltaba en la validación de categorías de gastos de la web.
- Borrado de coche: se eliminan explícitamente todos los registros hijos.
- `init_db()` **auto-repara** filas huérfanas en cada arranque.

### Cambiado
- Sustituido el backend de backup específico de OneDrive por copias locales.
- Gunicorn envía sus errores a la salida del contenedor para que
  `docker compose logs kmtracker` muestre los tracebacks.

## [1.0.0] - 2026-10

- Versión inicial publicada como software libre (AGPL-3.0).
