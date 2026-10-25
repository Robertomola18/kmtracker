"""Copias de seguridad locales (sin dependencias de OneDrive ni servicios).

Guarda un tar.gz con la base de datos SQLite en un directorio local y aplica
rotacion por numero de copias y/o por antiguedad. El directorio se puede montar
en un NAS, disco externo o carpeta sincronizada por el usuario.
"""
import contextlib
import os
import time
import tarfile
import tempfile
import threading
import logging
import shutil
import sqlite3

logger = logging.getLogger('kmtracker')

PREFIX = 'kmtracker_'
SUFFIX = '.tar.gz'
_restore_lock = threading.Lock()


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


def _remove_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        logger.warning('No se pudo borrar %s', path, exc_info=True)


def _remove_sidecars(db_path):
    for ext in ('-wal', '-shm'):
        _remove_file(db_path + ext)


def _validate_sqlite(path):
    try:
        conn = sqlite3.connect(path)
        try:
            result = conn.execute('PRAGMA integrity_check').fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError(f'Base de datos SQLite invalida: {exc}') from exc
    if not result or result[0] != 'ok':
        raise ValueError('La base de datos SQLite no pasa la comprobacion de integridad')


def _snapshot_database(db_path, dest_path):
    """Copia consistente usando la API de backup de SQLite (incluye WAL)."""
    tmp_path = dest_path + '.tmp'
    _remove_file(tmp_path)
    _remove_sidecars(tmp_path)
    src = sqlite3.connect(db_path)
    try:
        dst = sqlite3.connect(tmp_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    except Exception:
        _remove_file(tmp_path)
        raise
    finally:
        src.close()
    _remove_sidecars(dest_path)
    os.replace(tmp_path, dest_path)


def snapshot_database(db_path, dest_path):
    """Crea una copia consistente de una base de datos SQLite."""
    _validate_sqlite(db_path)
    _snapshot_database(db_path, dest_path)


@contextlib.contextmanager
def replaced_database(db_path, source_path):
    """Sustituye db_path por source_path de forma reversible.

    Valida la base de origen, elimina los sidecars WAL/SHM antiguos y guarda
    la base actual como <db_path>.bak. Si el bloque with lanza una excepcion,
    restaura automaticamente la base anterior.
    """
    with _restore_lock:
        _validate_sqlite(source_path)
        stage = db_path + '.restore_tmp'
        _remove_file(stage)
        try:
            _snapshot_database(source_path, stage)
            had_db = os.path.exists(db_path)
            backup_path = db_path + '.bak'
            if had_db:
                _snapshot_database(db_path, backup_path)
            try:
                _remove_sidecars(db_path)
                os.replace(stage, db_path)
                yield backup_path
            except Exception:
                _remove_file(db_path)
                _remove_sidecars(db_path)
                if had_db and os.path.exists(backup_path):
                    shutil.copy2(backup_path, db_path)
                raise
        finally:
            _remove_file(stage)


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


@contextlib.contextmanager
def restore_backup(db_path, name):
    """Restaura una copia concreta y permite ejecutar migraciones dentro del
    contexto. Si el bloque with falla, se recupera la base anterior."""
    name = safe_name(name)
    if not name:
        raise ValueError('Nombre de backup no valido')
    d = backup_dir(db_path)
    tar_path = os.path.join(d, name)
    if not os.path.isfile(tar_path):
        raise FileNotFoundError(name)

    tmpdir = os.path.join(d, '.restore')
    os.makedirs(tmpdir, exist_ok=True)
    extract_dir = tempfile.mkdtemp(prefix='restore_', dir=tmpdir)
    restored = os.path.join(extract_dir, 'kmtracker.db')
    try:
        with tarfile.open(tar_path, 'r:gz') as tar:
            member = next((m for m in tar.getmembers()
                           if m.isfile() and os.path.basename(m.name) == 'kmtracker.db'), None)
            if member is None:
                raise ValueError('El backup no contiene kmtracker.db')
            fsrc = tar.extractfile(member)
            if fsrc is None:
                raise ValueError('No se pudo leer kmtracker.db del backup')
            with fsrc, open(restored, 'wb') as fdst:
                shutil.copyfileobj(fsrc, fdst)
        with replaced_database(db_path, restored):
            yield name
        logger.info('Backup restaurado: %s', name)
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)


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
