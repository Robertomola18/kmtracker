"""Copias de seguridad locales (sin dependencias de OneDrive ni servicios).

Guarda un tar.gz con la base de datos SQLite en un directorio local y aplica
rotacion por numero de copias y/o por antiguedad. El directorio se puede montar
en un NAS, disco externo o carpeta sincronizada por el usuario.
"""
import os
import time
import tarfile
import logging
import sqlite3

logger = logging.getLogger('kmtracker')

PREFIX = 'kmtracker_'
SUFFIX = '.tar.gz'


def _env_int(name, default):
    try:
        return int(os.environ.get(name, '') or default)
    except (TypeError, ValueError):
        return default


def backup_dir(db_path):
    """Directorio de backups: KM_BACKUP_DIR, o <carpeta de la BD>/backups."""
    path = os.environ.get('KM_BACKUP_DIR') or os.path.join(os.path.dirname(
        os.path.abspath(db_path)), 'backups')
    os.makedirs(path, exist_ok=True)
    return path


def safe_name(name):
    """Solo permite nombres de fichero generados por esta app (sin rutas)."""
    base = os.path.basename(name or '')
    if base != name or not base.startswith(PREFIX) or not base.endswith(SUFFIX):
        return None
    return base


def create_backup(db_path):
    """Crea un tar.gz con la BD (usando la API de backup de SQLite, que
    funciona aunque la BD este en modo WAL). Devuelve el nombre del fichero."""
    d = backup_dir(db_path)
    name = f"{PREFIX}{time.strftime('%Y%m%d_%H%M%S')}{SUFFIX}"
    dest = os.path.join(d, name)
    tmp_db = os.path.join(d, '.tmp_backup.db')
    src = sqlite3.connect(db_path)
    try:
        dst = sqlite3.connect(tmp_db)
        src.backup(dst)
        dst.close()
    finally:
        src.close()
    try:
        with tarfile.open(dest, 'w:gz') as tar:
            tar.add(tmp_db, arcname='kmtracker.db')
    finally:
        if os.path.exists(tmp_db):
            os.remove(tmp_db)
    prune_backups(db_path)
    logger.info('Backup creado: %s', name)
    return name


def list_backups(db_path):
    """Lista los backups como dicts {name, size, mtime}, del mas nuevo al mas
    antiguo."""
    d = backup_dir(db_path)
    out = []
    for fn in os.listdir(d):
        if safe_name(fn):
            p = os.path.join(d, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue
            out.append({'name': fn, 'size': st.st_size, 'mtime': st.st_mtime})
    out.sort(key=lambda x: x['mtime'], reverse=True)
    return out


def restore_backup(db_path, name):
    """Restaura una copia concreta. Hace un swap atomico y guarda la BD actual
    como <db>.bak. Lanza ValueError si el nombre no es valido."""
    name = safe_name(name)
    if not name:
        raise ValueError('Nombre de backup no valido')
    d = backup_dir(db_path)
    tar_path = os.path.join(d, name)
    if not os.path.isfile(tar_path):
        raise FileNotFoundError(name)

    tmpdir = os.path.join(d, '.restore')
    os.makedirs(tmpdir, exist_ok=True)
    extract_dir = os.path.join(tmpdir, name)
    os.makedirs(extract_dir, exist_ok=True)
    with tarfile.open(tar_path, 'r:gz') as tar:
        member = next((m for m in tar.getmembers()
                       if m.isfile() and os.path.basename(m.name) == 'kmtracker.db'), None)
        if member is None:
            raise ValueError('El backup no contiene kmtracker.db')
        tar.extract(member, path=extract_dir)
    restored = os.path.join(extract_dir, member.name)

    stage = db_path + '.restore_tmp'
    with open(restored, 'rb') as fsrc, open(stage, 'wb') as fdst:
        while True:
            chunk = fsrc.read(256 * 1024)
            if not chunk:
                break
            fdst.write(chunk)
    for ext in ('-wal', '-shm'):
        side = db_path + ext
        if os.path.exists(side):
            os.remove(side)
    if os.path.exists(db_path):
        os.replace(db_path, db_path + '.bak')
    try:
        os.replace(stage, db_path)
    except Exception:
        if os.path.exists(stage):
            os.remove(stage)
        raise
    logger.info('Backup restaurado: %s', name)
    return name


def delete_backup(db_path, name):
    name = safe_name(name)
    if not name:
        raise ValueError('Nombre de backup no valido')
    p = os.path.join(backup_dir(db_path), name)
    if os.path.isfile(p):
        os.remove(p)
        return True
    return False


def prune_backups(db_path):
    """Rotacion: conserva KM_BACKUP_KEEP_COUNT copias (10 por defecto) y borra
    las mas antiguas que KM_BACKUP_KEEP_DAYS dias (30 por defecto)."""
    keep_count = _env_int('KM_BACKUP_KEEP_COUNT', 10)
    keep_days = _env_int('KM_BACKUP_KEEP_DAYS', 30)
    backups = list_backups(db_path)
    limite = time.time() - keep_days * 86400
    borrados = []
    for b in backups[keep_count:]:
        if b['mtime'] >= limite:
            continue
        try:
            delete_backup(db_path, b['name'])
            borrados.append(b['name'])
        except OSError:
            logger.warning('No se pudo borrar el backup %s', b['name'])
    return borrados
