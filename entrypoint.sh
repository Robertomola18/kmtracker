#!/bin/sh
set -e

# Crear directorios necesarios
mkdir -p /app/static/uploads /data

# Generar secret key persistente en el volumen de datos
KEY_FILE="/data/.secret_key"
if [ ! -f "$KEY_FILE" ]; then
    python3 -c "import secrets; print(secrets.token_hex(24))" > "$KEY_FILE"
fi
ln -sf "$KEY_FILE" /app/.secret_key

export KMTRACKER_DB_PATH="${KMTRACKER_DB_PATH:-/data/kmtracker.db}"
export KMTRACKER_DEBUG=0

# Inicializar BD y crear la contrasena si aun no existe (desde env var)
python3 -c "
import os
from models import init_db, init_settings, get_db
from werkzeug.security import generate_password_hash
init_db()
init_settings()
conn = get_db()
row = conn.execute(\"SELECT value FROM settings WHERE key='password_hash'\").fetchone()
if not row:
    password = os.environ.get('KMTRACKER_PASSWORD')
    if not password:
        raise SystemExit('KMTRACKER_PASSWORD no definida: define una contrasena '
                         'para el acceso web (variable de entorno).')
    pw = generate_password_hash(password)
    conn.execute(\"INSERT OR REPLACE INTO settings (key, value) VALUES ('password_hash', ?)\", (pw,))
    conn.commit()
    print('Password hash creado.')
conn.close()
"

exec "$@"
