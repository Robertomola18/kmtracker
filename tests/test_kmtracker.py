import io
import re
import sqlite3
import os

import pytest


def _get_csrf(client):
    html = client.get('/login').get_data(as_text=True)
    m = re.search(r'name="_csrf" value="([^"]+)"', html)
    assert m, 'csrf token no encontrado'
    return m.group(1)


def test_init_db_creates_tables(km_db_path):
    from models import get_db
    conn = get_db()
    tables = {r['name'] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert 'cars' in tables
    assert 'settings' in tables
    assert 'fuel' in tables


def test_wal_journal_mode(km_db_path):
    from models import get_db
    conn = get_db()
    mode = conn.execute('PRAGMA journal_mode').fetchone()[0]
    conn.close()
    assert mode == 'wal'


def test_root_redirects_to_login_or_panel(client):
    resp = client.get('/')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/login')


def test_login_correct_password(logged_client):
    resp = logged_client.get('/panel')
    assert resp.status_code == 200


def test_login_wrong_password_rejected(client):
    token = _get_csrf(client)
    resp = client.post('/login', data={'password': 'incorrecta', '_csrf': token})
    assert resp.status_code == 200
    assert b'Contrase' in resp.get_data() or b'password' in resp.get_data().lower()


def test_admin_restore_get_page(logged_client):
    resp = logged_client.get('/admin/restore')
    assert resp.status_code == 200
    assert b'enctype="multipart/form-data"' in resp.data
    assert b'name="database"' in resp.data
    assert logged_client.get('/admin/restore/').status_code == 200


def test_admin_restore_oversized_redirects(km, logged_client):
    old_limit = km.app.config['MAX_CONTENT_LENGTH']
    km.app.config['MAX_CONTENT_LENGTH'] = 64
    try:
        csrf = _get_csrf(logged_client)
        resp = logged_client.post(
            '/admin/restore',
            data={'database': (io.BytesIO(b'x' * 256), 'grande.db'), '_csrf': csrf},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/admin')
    finally:
        km.app.config['MAX_CONTENT_LENGTH'] = old_limit


def test_admin_backup_download_is_sqlite(logged_client):
    resp = logged_client.get('/admin/backup')
    assert resp.status_code == 200
    assert resp.data[:16] == b'SQLite format 3\x00'
    resp.close()


def test_restore_accepts_valid_sqlite(logged_client):
    from models import DB_PATH
    csrf = _get_csrf(logged_client)
    sentinel = os.path.join(os.path.dirname(DB_PATH), 'sentinel_upload.db')
    conn = sqlite3.connect(sentinel)
    conn.execute("CREATE TABLE sentinel (x INTEGER)")
    conn.commit()
    conn.close()

    resp = logged_client.post('/admin/restore',
                              data={'database': (open(sentinel, 'rb'), 'kmtracker.db'), '_csrf': csrf},
                              content_type='multipart/form-data')
    os.unlink(sentinel)
    assert resp.status_code == 302
    conn = sqlite3.connect(DB_PATH)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert 'sentinel' in tables


def test_restore_rejects_non_sqlite(logged_client):
    csrf = _get_csrf(logged_client)
    resp = logged_client.post('/admin/restore',
                              data={'database': (io.BytesIO(b'not a database'), 'falso.db'), '_csrf': csrf},
                              content_type='multipart/form-data')
    assert resp.status_code == 302


# --- Gastos: coma decimal y categoria 'mejoras' ---------------------------

def _csrf_page(client, url):
    html = client.get(url).get_data(as_text=True)
    m = re.search(r'name="_csrf" value="([^"]+)"', html)
    assert m, f'no se encontro csrf en {url}'
    return m.group(1)


@pytest.fixture
def gastos_env(km):
    """BD lista + cliente logueado + un coche de prueba.

    Reconstruye el esquema y el password y hace su propio login porque
    test_restore_accepts_valid_sqlite reinicia la BD de sesion (la deja sin
    password_hash), asi que aqui no se puede depender de logged_client."""
    import models
    from models import init_db, init_settings, set_setting
    from werkzeug.security import generate_password_hash
    init_db()
    init_settings()
    set_setting('password_hash', generate_password_hash('test-password'))
    client = km.app.test_client()
    html = client.get('/login').get_data(as_text=True)
    m = re.search(r'name="_csrf" value="([^"]+)"', html)
    assert m, 'no se encontro csrf en login'
    client.post('/login', data={'password': 'test-password', '_csrf': m.group(1)})

    mat = '7777GTS'
    conn = models.get_db()
    conn.execute("DELETE FROM expenses WHERE car_id IN (SELECT id FROM cars WHERE matricula=?)", (mat,))
    conn.execute("DELETE FROM cars WHERE matricula=?", (mat,))
    conn.execute(
        "INSERT INTO cars (matricula, modelo, anyo, modo, km_inicial, km_actual, es_prueba)"
        " VALUES (?, 'GastosTest', 2020, 'total', 0, 0, 0)", (mat,))
    conn.commit()
    car_id = conn.execute("SELECT id FROM cars WHERE matricula=?", (mat,)).fetchone()['id']
    conn.close()
    yield {'id': car_id, 'mat': mat, 'client': client}
    conn = models.get_db()
    conn.execute("DELETE FROM expenses WHERE car_id=?", (car_id,))
    conn.execute("DELETE FROM cars WHERE id=?", (car_id,))
    conn.commit()
    conn.close()


def test_num_tolera_coma_decimal(km):
    assert km._num('25,50') == 25.5
    assert km._num('1.234,56') == 1234.56  # separador de miles con punto
    assert km._num('40') == 40.0
    assert km._num('') is None
    assert km._num(None) is None
    assert km._num('abc') is None


def test_alta_gasto_acepta_coma_decimal_y_mejoras(km, gastos_env):
    import models
    client = gastos_env['client']
    url = f"/coche/{gastos_env['mat']}/gastos"
    csrf = _csrf_page(client, url)
    resp = client.post(url, data={
        'concepto': 'Prueba coma', 'coste': '25,50', 'categoria': 'mejoras',
        'fecha': '2026-01-15', '_csrf': csrf,
    }, follow_redirects=True)
    assert resp.status_code == 200
    filas = [e for e in models.get_expenses(gastos_env['id']) if e['concepto'] == 'Prueba coma']
    assert filas, 'el gasto con coma decimal no se guardo'
    assert filas[0]['coste'] == 25.5
    assert filas[0]['categoria'] == 'mejoras'


def test_editar_gasto_acepta_coma_y_mejoras(km, gastos_env):
    import models
    client = gastos_env['client']
    models.add_expense(gastos_env['id'], '2026-01-16', 'Rueda nueva', 120, 'reparacion')
    exp = [e for e in models.get_expenses(gastos_env['id']) if e['concepto'] == 'Rueda nueva'][0]
    url = f"/coche/{gastos_env['mat']}/gastos/{exp['id']}/editar"
    csrf = _csrf_page(client, url)
    resp = client.post(url, data={
        'concepto': 'Rueda nueva', 'coste': '120,00', 'categoria': 'mejoras',
        'fecha': '2026-01-16', '_csrf': csrf,
    }, follow_redirects=True)
    assert resp.status_code == 200
    upd = [e for e in models.get_expenses(gastos_env['id']) if e['id'] == exp['id']][0]
    assert upd['categoria'] == 'mejoras'
    assert upd['coste'] == 120.0


def test_esquema_expenses_admite_mejoras(km):
    from models import get_db
    conn = get_db()
    row = conn.execute("SELECT sql FROM sqlite_master WHERE name='expenses'").fetchone()
    conn.close()
    assert row and "'mejoras'" in row[0]


# --- Integridad referencial: filas huerfanas --------------------------------

def _scalar(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()[0]


def test_delete_car_no_deja_huerfanos(km):
    import models
    from models import init_db, get_db
    init_db()
    conn = get_db()
    car_id = conn.execute(
        "INSERT INTO cars (matricula, modelo, anyo, modo, km_inicial, km_actual, es_prueba)"
        " VALUES ('5555ORF', 'Orfano', 2020, 'total', 0, 0, 0)").lastrowid
    item_id = conn.execute(
        "INSERT INTO maintenance_items (car_id, nombre, intervalo_km, km_ultimo)"
        " VALUES (?, 'Filtro', 10000, 0)", (car_id,)).lastrowid
    conn.execute("INSERT INTO alerts (item_id, km_disparo) VALUES (?, 10000)", (item_id,))
    conn.execute("INSERT INTO entries (car_id, fecha, tipo, lectura, is_reset)"
                 " VALUES (?, '2026-01-01', 'total', 100, 0)", (car_id,))
    conn.execute("INSERT INTO fuel (car_id, fecha, litros, precio_litro, total_gasto,"
                 " tipo_combustible, tanque_lleno)"
                 " VALUES (?, '2026-01-01', 40, 1.5, 60, 'gasolina', 1)", (car_id,))
    exp_id = conn.execute(
        "INSERT INTO expenses (car_id, fecha, concepto, coste, categoria)"
        " VALUES (?, '2026-01-01', 'X', 10, 'otro')", (car_id,)).lastrowid
    conn.execute("INSERT INTO expense_photos (expense_id, filename, data)"
                 " VALUES (?, 'f.png', ?)", (exp_id, b'x'))
    rec_id = conn.execute(
        "INSERT INTO maintenance_records (car_id, fecha, km, coste)"
        " VALUES (?, '2026-01-01', 100, 50)", (car_id,)).lastrowid
    conn.execute("INSERT INTO maintenance_record_items (record_id, item_id) VALUES (?, ?)",
                 (rec_id, item_id))
    conn.execute("INSERT INTO maintenance_photos (record_id, filename, data)"
                 " VALUES (?, 'p.png', ?)", (rec_id, b'x'))
    conn.execute("INSERT INTO documents (car_id, titulo, filename, data)"
                 " VALUES (?, 't', 'd.pdf', ?)", (car_id, b'x'))
    conn.commit()
    conn.close()

    models.delete_car(car_id)

    conn = get_db()
    huerfanos = conn.execute("PRAGMA foreign_key_check").fetchall()
    assert huerfanos == [], f'quedan huerfanos: {huerfanos}'
    assert _scalar(conn, "SELECT COUNT(*) FROM cars WHERE id=?", (car_id,)) == 0
    for tabla in ('maintenance_items', 'maintenance_records', 'entries', 'fuel',
                  'expenses', 'documents'):
        assert _scalar(conn, f"SELECT COUNT(*) FROM {tabla} WHERE car_id=?", (car_id,)) == 0, tabla
    conn.close()


def test_init_db_purga_huerfanos(km):
    import models
    from models import init_db, get_db
    init_db()
    conn = get_db()
    car_id = conn.execute(
        "INSERT INTO cars (matricula, modelo, anyo, modo, km_inicial, km_actual, es_prueba)"
        " VALUES ('6666HUE', 'Huerfano', 2020, 'total', 0, 0, 0)").lastrowid
    conn.execute("INSERT INTO maintenance_items (car_id, nombre, intervalo_km, km_ultimo)"
                 " VALUES (?, 'Filtro', 10000, 0)", (car_id,))
    conn.execute("INSERT INTO expenses (car_id, fecha, concepto, coste, categoria)"
                 " VALUES (?, '2026-01-01', 'X', 5, 'otro')", (car_id,))
    # Simula el borrado historico con las foreign keys desactivadas.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DELETE FROM cars WHERE id=?", (car_id,))
    conn.commit()
    queda = _scalar(conn, "SELECT COUNT(*) FROM maintenance_items WHERE car_id=?", (car_id,))
    conn.close()
    assert queda == 1, 'no se pudo simular el huerfano'

    models.init_db()

    conn = get_db()
    assert _scalar(conn, "SELECT COUNT(*) FROM maintenance_items WHERE car_id=?", (car_id,)) == 0
    assert _scalar(conn, "SELECT COUNT(*) FROM expenses WHERE car_id=?", (car_id,)) == 0
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()


def test_backup_crear_listar_borrar(km_db_path, tmp_path, monkeypatch):
    import backup
    monkeypatch.setenv('KM_BACKUP_DIR', str(tmp_path))
    monkeypatch.setenv('KM_BACKUP_KEEP_COUNT', '10')
    name = backup.create_backup(km_db_path)
    assert name.startswith('kmtracker_') and name.endswith('.tar.gz')
    assert os.path.exists(os.path.join(str(tmp_path), name))

    backups = backup.list_backups(km_db_path)
    assert any(b['name'] == name for b in backups)
    assert all('size' in b and 'mtime' in b for b in backups)

    assert backup.safe_name('../evil.tar.gz') is None
    assert backup.safe_name('otra_cosa.tar.gz') is None

    assert backup.delete_backup(km_db_path, name) is True
    assert backup.list_backups(km_db_path) == []


def _make_test_db(path, value):
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE items (v TEXT)')
    conn.execute('INSERT INTO items (v) VALUES (?)', (value,))
    conn.commit()
    conn.close()


def _read_test_db(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute('SELECT v FROM items').fetchone()[0]
    finally:
        conn.close()


def test_replaced_database_keeps_backup_and_removes_sidecars(tmp_path):
    import backup
    live = str(tmp_path / 'live.db')
    source = str(tmp_path / 'source.db')
    _make_test_db(live, 'anterior')
    _make_test_db(source, 'nueva')

    live_conn = sqlite3.connect(live)
    live_conn.execute('PRAGMA journal_mode=WAL')
    live_conn.execute('PRAGMA wal_autocheckpoint=0')
    live_conn.execute("UPDATE items SET v='anterior'")
    live_conn.commit()
    assert os.path.exists(live + '-wal')

    try:
        with backup.replaced_database(live, source) as backup_path:
            assert _read_test_db(live) == 'nueva'
            assert backup_path == live + '.bak'

        assert _read_test_db(live) == 'nueva'
        assert _read_test_db(live + '.bak') == 'anterior'
        assert not os.path.exists(live + '-wal')
        assert not os.path.exists(live + '-shm')
    finally:
        live_conn.close()


def test_replaced_database_rolls_back_on_error(tmp_path):
    import backup
    live = str(tmp_path / 'live.db')
    source = str(tmp_path / 'source.db')
    _make_test_db(live, 'anterior')
    _make_test_db(source, 'nueva')

    with pytest.raises(RuntimeError, match='fallo simulado'):
        with backup.replaced_database(live, source):
            assert _read_test_db(live) == 'nueva'
            raise RuntimeError('fallo simulado')

    assert _read_test_db(live) == 'anterior'
    assert _read_test_db(live + '.bak') == 'anterior'
    assert not os.path.exists(live + '-wal')
    assert not os.path.exists(live + '-shm')


def test_restore_backup_context(tmp_path, monkeypatch):
    import backup
    monkeypatch.setenv('KM_BACKUP_DIR', str(tmp_path / 'backups'))
    live = str(tmp_path / 'live.db')
    _make_test_db(live, 'original')
    name = backup.create_backup(live)

    conn = sqlite3.connect(live)
    conn.execute("UPDATE items SET v='cambiada'")
    conn.commit()
    conn.close()

    with backup.restore_backup(live, name) as restored_name:
        assert restored_name == name
        assert _read_test_db(live) == 'original'

    assert _read_test_db(live) == 'original'
    assert _read_test_db(live + '.bak') == 'cambiada'
