# Changelog

Todas las versiones notables de KMtracker.

## [Sin publicar]

### Seguridad
- Actualizadas dependencias: WeasyPrint 70.0 (Pillow 13), requests 2.34.2,
  Werkzeug 3.1.9, MarkupSafe 3.0.4, click 8.5.0, gunicorn 26.2.0,
  certifi 2026.10.23 y brotli 1.2.1; auditoría OSV sin vulnerabilidades conocidas.
- Imagen base Debian con `apt-get upgrade` y `pip`/`setuptools`/`wheel` al día.

### Añadido
- Soporte de categoría de gasto **"Mejoras"** y aceptación de **coma decimal**
  en todos los campos numéricos de los formularios.
- **Copias de seguridad locales rotativas** desde `/admin` (crear, listar,
  descargar, restaurar, borrar), sin depender de servicios externos.
- **Lista blanca** de usuarios para el bot de Telegram
  (`TELEGRAM_ALLOWED_USER_IDS` / ajuste `telegram_allowed_ids`).
- Bot de Telegram empaquetado como **servicio opcional** (`--profile bot`).

### Corregido
- `mantenimiento` faltaba en la validación de categorías de gastos de la web.
- Borrado de coche: se eliminan explícitamente todos los registros hijos.
- `init_db()` **auto-repara** filas huérfanas en cada arranque.

### Cambiado
- Sustituido el backend de backup específico de OneDrive por copias locales.

## [1.0.0] - 2026-10

- Versión inicial publicada como software libre (AGPL-3.0).
