import sqlite3
import os
import re
import calendar
import logging
from datetime import datetime, date

logger = logging.getLogger('kmtracker')

DB_PATH = os.environ.get('KMTRACKER_DB_PATH') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kmtracker.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn

def _purge_orphans(conn):
    """Elimina filas huerfanas que puedan quedar de borrados antiguos (p. ej.
    un coche borrado mientras las foreign keys estaban desactivadas). Es
    idempotente: se ejecuta en cada init_db() para que cualquier instalacion
    se auto-repare al arrancar.

    Orden hijo -> padre para no depender unicamente del ON DELETE CASCADE.
    Devuelve el numero de filas eliminadas."""
    checks = (
        ('alerts', "item_id NOT IN (SELECT id FROM maintenance_items)"),
        ('maintenance_record_items',
         "record_id NOT IN (SELECT id FROM maintenance_records) "
         "OR item_id NOT IN (SELECT id FROM maintenance_items)"),
        ('maintenance_photos', "record_id NOT IN (SELECT id FROM maintenance_records)"),
        ('expense_photos', "expense_id NOT IN (SELECT id FROM expenses)"),
        ('documents', "car_id NOT IN (SELECT id FROM cars)"),
        ('expenses', "car_id NOT IN (SELECT id FROM cars)"),
        ('maintenance_records', "car_id NOT IN (SELECT id FROM cars)"),
        ('entries', "car_id NOT IN (SELECT id FROM cars)"),
        ('fuel', "car_id NOT IN (SELECT id FROM cars)"),
        ('maintenance_items', "car_id NOT IN (SELECT id FROM cars)"),
    )
    borrados = 0
    conn.execute("BEGIN")
    try:
        for tabla, cond in checks:
            cur = conn.execute(f"DELETE FROM {tabla} WHERE {cond}")
            if cur.rowcount and cur.rowcount > 0:
                borrados += cur.rowcount
                logger.warning('init_db: %d fila(s) huerfana(s) en %s eliminada(s)',
                               cur.rowcount, tabla)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception('init_db: fallo purgando huerfanos (se ignora)')
    return borrados


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE NOT NULL,
            modelo TEXT NOT NULL,
            anyo INTEGER NOT NULL,
            modo TEXT NOT NULL CHECK(modo IN ('partial', 'total')),
            km_inicial REAL NOT NULL DEFAULT 0,
            km_actual REAL NOT NULL DEFAULT 0,
            pais TEXT NOT NULL DEFAULT 'es' CHECK(pais IN ('es', 'pt')),
            es_prueba INTEGER NOT NULL DEFAULT 0,
            seguro_fecha TEXT,
            itv_fecha TEXT,
            impuesto_fecha TEXT,
            foto TEXT,
            motor TEXT,
            bastidor TEXT,
            fecha_baja TEXT
        );        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('partial', 'total', 'correction')),
            lectura REAL NOT NULL,
            is_reset INTEGER NOT NULL DEFAULT 0,
            km_calculados REAL,
            km_acumulado REAL,
            nota TEXT,
            FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS fuel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            litros REAL NOT NULL,
            precio_litro REAL NOT NULL,
            total_gasto REAL NOT NULL,
            km_lectura REAL,
            tipo_combustible TEXT NOT NULL CHECK(tipo_combustible IN ('gasolina', 'diesel')),
            tanque_lleno INTEGER NOT NULL DEFAULT 0,
            nota TEXT,
            FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS maintenance_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            intervalo_km REAL NOT NULL,
            km_ultimo REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            km_disparo REAL NOT NULL,
            leida INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (item_id) REFERENCES maintenance_items(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            concepto TEXT NOT NULL,
            coste REAL NOT NULL,
            categoria TEXT NOT NULL CHECK(categoria IN ('seguro', 'itv', 'impuesto', 'reparacion', 'limpieza', 'mantenimiento', 'mejoras', 'otro')),
            km_lectura REAL,
            nota TEXT,
            foto TEXT,
            FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()

    for col in ('seguro_fecha', 'itv_fecha', 'impuesto_fecha', 'foto', 'motor', 'bastidor'):
        try:
            conn.execute(f"ALTER TABLE cars ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("ALTER TABLE cars ADD COLUMN desv_km REAL NOT NULL DEFAULT 100")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE expenses ADD COLUMN foto TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE cars ADD COLUMN foto_data BLOB")
    except sqlite3.OperationalError:
        pass
    # Fecha de baja (venta) del vehiculo. NULL = sigue en servicio.
    # Los movimientos con fecha <= fecha_baja siguen contando en el historico.
    try:
        conn.execute("ALTER TABLE cars ADD COLUMN fecha_baja TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE maintenance_photos ADD COLUMN data BLOB")
    except sqlite3.OperationalError:
        pass

    # Migración: ampliar CHECK de pais para motos (moto_es / moto_pt)
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cars'").fetchone()
    if row and 'moto_es' not in (row[0] or ''):
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript("""
            BEGIN;
            CREATE TABLE cars_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matricula TEXT UNIQUE NOT NULL,
                modelo TEXT NOT NULL,
                anyo INTEGER NOT NULL,
                modo TEXT NOT NULL CHECK(modo IN ('partial', 'total')),
                km_inicial REAL NOT NULL DEFAULT 0,
                km_actual REAL NOT NULL DEFAULT 0,
                pais TEXT NOT NULL DEFAULT 'es' CHECK(pais IN ('es', 'pt', 'moto_es', 'moto_pt')),
                es_prueba INTEGER NOT NULL DEFAULT 0,
                seguro_fecha TEXT,
                itv_fecha TEXT,
                impuesto_fecha TEXT,
                foto TEXT,
                motor TEXT,
                bastidor TEXT,
                desv_km REAL NOT NULL DEFAULT 100,
                foto_data BLOB,
                fecha_baja TEXT
            );
            INSERT INTO cars_new (
                id, matricula, modelo, anyo, modo, km_inicial, km_actual,
                pais, es_prueba, seguro_fecha, itv_fecha, impuesto_fecha,
                foto, motor, bastidor, desv_km, foto_data, fecha_baja
            ) SELECT
                id, matricula, modelo, anyo, modo, km_inicial, km_actual,
                pais, es_prueba, seguro_fecha, itv_fecha, impuesto_fecha,
                foto, motor, bastidor, desv_km, foto_data, fecha_baja
            FROM cars;
            DROP TABLE cars;
            ALTER TABLE cars_new RENAME TO cars;
            COMMIT;
        """)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    # Migración: ampliar CHECK de expenses con categoria 'mantenimiento'
    # y eliminar gastos duplicados auto-creados desde maintenance_records.
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='expenses'").fetchone()
    if row and 'mantenimiento' not in (row[0] or ''):
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript("""
            BEGIN;
            CREATE TABLE expenses_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                concepto TEXT NOT NULL,
                coste REAL NOT NULL,
                categoria TEXT NOT NULL CHECK(categoria IN ('seguro', 'itv', 'impuesto', 'reparacion', 'limpieza', 'mantenimiento', 'mejoras', 'otro')),
                km_lectura REAL,
                nota TEXT,
                foto TEXT,
                FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
            );
            INSERT INTO expenses_new SELECT * FROM expenses;
            DROP TABLE expenses;
            ALTER TABLE expenses_new RENAME TO expenses;
            COMMIT;
        """)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    # Migración: ampliar CHECK de expenses con la categoria 'mejoras'.
    # Se listan las columnas explicitas (no SELECT *) para tolerar BDs antiguas
    # que aun no tuvieran la columna foto.
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='expenses'").fetchone()
    if row and 'mejoras' not in (row[0] or ''):
        has_foto = any(r['name'] == 'foto' for r in conn.execute("PRAGMA table_info(expenses)"))
        foto_col = 'foto' if has_foto else 'NULL'
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(f"""
            BEGIN;
            CREATE TABLE expenses_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                concepto TEXT NOT NULL,
                coste REAL NOT NULL,
                categoria TEXT NOT NULL CHECK(categoria IN ('seguro', 'itv', 'impuesto', 'reparacion', 'limpieza', 'mantenimiento', 'mejoras', 'otro')),
                km_lectura REAL,
                nota TEXT,
                foto TEXT,
                FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
            );
            INSERT INTO expenses_new (id, car_id, fecha, concepto, coste, categoria, km_lectura, nota, foto)
                SELECT id, car_id, fecha, concepto, coste, categoria, km_lectura, nota, {foto_col} FROM expenses;
            DROP TABLE expenses;
            ALTER TABLE expenses_new RENAME TO expenses;
            COMMIT;
        """)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    # Eliminar gastos duplicados auto-creados por maintenance_records
    # (cada mantenimiento cuenta una sola vez, desde maintenance_records.coste).
    conn.execute("DELETE FROM expenses WHERE concepto = 'Mantenimiento / Reparacion'")
    conn.commit()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS maintenance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            km REAL NOT NULL,
            coste REAL,
            nota TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS maintenance_record_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            FOREIGN KEY (record_id) REFERENCES maintenance_records(id) ON DELETE CASCADE,
            FOREIGN KEY (item_id) REFERENCES maintenance_items(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS maintenance_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            tipo TEXT DEFAULT 'general',
            data BLOB,
            FOREIGN KEY (record_id) REFERENCES maintenance_records(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS expense_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            data BLOB NOT NULL,
            FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            filename TEXT NOT NULL,
            data BLOB NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    _purge_orphans(conn)
    conn.close()
    init_settings()


def get_all_cars():
    """Todos los coches, incluidos prueba y vendidos (que se ocultan de las
    estadisticas pero siguen siendo consultables). Orden: primero los que
    estan en servicio, despues los de prueba y por ultimo los ya vendidos."""
    conn = get_db()
    cars = conn.execute(
        "SELECT * FROM cars ORDER BY CASE"
        " WHEN es_prueba = 1 THEN 1"
        " WHEN fecha_baja IS NOT NULL AND fecha_baja <= date('now') THEN 2"
        " ELSE 0 END ASC, modelo ASC"
    ).fetchall()
    conn.close()
    return [_car_dict(dict(c)) for c in cars]


def _car_dict(d):
    if d.get('foto_data'):
        # El parametro ?v= cambia cuando cambia la foto; sin el, el navegador
        # sirve la version cacheada (SEND_FILE_MAX_AGE_DEFAULT=86400) y parece
        # que "no deja" actualizarla.
        d['foto_url'] = f"/car_photo/{d['id']}?v={len(d['foto_data'])}"
    elif d.get('foto'):
        d['foto_url'] = f"/static/{d['foto']}"
    else:
        d['foto_url'] = None
    return d


def get_car(car_id=None, matricula=None):
    conn = get_db()
    if car_id:
        car = conn.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
    else:
        car = conn.execute("SELECT * FROM cars WHERE matricula = ?", (matricula,)).fetchone()
    conn.close()
    return _car_dict(dict(car)) if car else None


def _norm_matricula(matricula):
    """Normaliza matrícula: mayúsculas, sin espacios ni guiones ni símbolos raros."""
    if not matricula:
        return ''
    return re.sub(r'[^A-Z0-9]', '', matricula.upper().strip())


def _validar_matricula(matricula, pais):
    """Valida formato de matrícula según país. Devuelve (ok, motivo).
    Acepta formatos modernos e históricos (ES/PT/moto); solo rechaza
    cadenas claramente inválidas para no romper datos existentes."""
    if not matricula or len(matricula) < 4:
        return False, 'Matrícula inválida'
    # formato del país pedido
    formato_pais = {
        'es': r'\d{4}[A-Z]{3}',
        'pt': r'(?:[A-Z]{2}\d{2}[A-Z]{2}|\d{2}[A-Z]{2}\d{2}|\d{4}[A-Z]{2})',
    }
    if pais == 'es' and re.fullmatch(formato_pais['es'], matricula):
        return True, None
    if pais == 'pt' and re.fullmatch(formato_pais['pt'], matricula):
        return True, None
    # motos: flexible, letras + dígitos
    if pais in ('moto_es', 'moto_pt') and re.fullmatch(r'[A-Z]?\d{1,4}[A-Z]{1,3}', matricula):
        return True, None
    # formatos de otros países / históricos: aceptar si solo son alfanuméricos
    if re.fullmatch(r'[A-Z0-9]{4,7}', matricula):
        return True, None
    return False, 'Matrícula inválida'


def add_car(matricula, modelo, anyo, modo, pais='es', km_inicial=0, es_prueba=0, motor='', bastidor=''):
    conn = get_db()
    matricula = _norm_matricula(matricula)
    if not matricula:
        return None, 'Matrícula inválida'
    ok, motivo = _validar_matricula(matricula, pais)
    if not ok:
        return None, motivo
    try:
        conn.execute("""
            INSERT INTO cars (matricula, modelo, anyo, modo, km_inicial, km_actual, pais, es_prueba, motor, bastidor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (matricula, modelo, anyo, modo, km_inicial, km_inicial, pais, es_prueba, motor, bastidor))
        conn.commit()
        car_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for nombre, intervalo in [
            ('Cambio aceite + filtro', 15000),
            ('Correa distribucion', 90000),
            ('Filtro aire', 30000),
            ('Pastillas freno', 40000),
        ]:
            conn.execute("""
                INSERT INTO maintenance_items (car_id, nombre, intervalo_km, km_ultimo)
                VALUES (?, ?, ?, ?)
            """, (car_id, nombre, intervalo, km_inicial))
        conn.commit()
        return car_id, None
    except sqlite3.IntegrityError:
        return None, "Ya existe un coche con esa matricula"
    finally:
        conn.close()


def update_car(car_id, matricula, modelo, anyo, modo, pais, es_prueba, km_inicial=None, km_actual=None, motor='', bastidor='', desv_km=None):
    conn = get_db()
    matricula = _norm_matricula(matricula)
    if not matricula:
        return False, 'Matrícula inválida'
    ok, motivo = _validar_matricula(matricula, pais)
    if not ok:
        return False, motivo
    try:
        fields = ["matricula=?", "modelo=?", "anyo=?", "modo=?", "pais=?", "es_prueba=?", "motor=?", "bastidor=?"]
        params = [matricula, modelo, anyo, modo, pais, es_prueba, motor, bastidor]
        if km_inicial is not None:
            fields.append("km_inicial=?")
            params.append(km_inicial)
        if km_actual is not None:
            fields.append("km_actual=?")
            params.append(km_actual)
        if desv_km is not None:
            fields.append("desv_km=?")
            params.append(desv_km)
        params.append(car_id)
        conn.execute(f"UPDATE cars SET {', '.join(fields)} WHERE id=?", params)
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Ya existe un coche con esa matricula"
    finally:
        conn.close()


def delete_car(car_id):
    conn = get_db()
    car = conn.execute("SELECT modelo, matricula FROM cars WHERE id=?", (car_id,)).fetchone()
    if car:
        # Borrado explicito de hijos en orden (hijo -> padre). No dependemos
        # solo de ON DELETE CASCADE: si el borrado del coche se hiciera con las
        # foreign keys desactivadas quedarian filas huerfanas.
        conn.execute("BEGIN")
        conn.execute(
            "DELETE FROM alerts WHERE item_id IN "
            "(SELECT id FROM maintenance_items WHERE car_id=?)", (car_id,))
        conn.execute(
            "DELETE FROM maintenance_record_items "
            "WHERE record_id IN (SELECT id FROM maintenance_records WHERE car_id=?) "
            "OR item_id IN (SELECT id FROM maintenance_items WHERE car_id=?)",
            (car_id, car_id))
        conn.execute(
            "DELETE FROM maintenance_photos WHERE record_id IN "
            "(SELECT id FROM maintenance_records WHERE car_id=?)", (car_id,))
        conn.execute(
            "DELETE FROM expense_photos WHERE expense_id IN "
            "(SELECT id FROM expenses WHERE car_id=?)", (car_id,))
        conn.execute("DELETE FROM documents WHERE car_id=?", (car_id,))
        conn.execute("DELETE FROM expenses WHERE car_id=?", (car_id,))
        conn.execute("DELETE FROM maintenance_records WHERE car_id=?", (car_id,))
        conn.execute("DELETE FROM entries WHERE car_id=?", (car_id,))
        conn.execute("DELETE FROM fuel WHERE car_id=?", (car_id,))
        conn.execute("DELETE FROM maintenance_items WHERE car_id=?", (car_id,))
        conn.execute("DELETE FROM cars WHERE id=?", (car_id,))
        conn.commit()
        conn.close()
        return dict(car)
    conn.close()
    return None


def update_car_foto(car_id, filename, data):
    conn = get_db()
    conn.execute("UPDATE cars SET foto=?, foto_data=? WHERE id=?", (filename, data, car_id))
    conn.commit()
    conn.close()


def add_entry(car_id, fecha, tipo, lectura, is_reset=False, nota=''):
    conn = get_db()
    car = conn.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
    if not car:
        conn.close()
        return None, "Coche no encontrado"

    car = dict(car)
    last_entry = conn.execute(
        "SELECT * FROM entries WHERE car_id = ? ORDER BY id DESC LIMIT 1",
        (car_id,)
    ).fetchone()

    if tipo == 'partial':
        if is_reset:
            km_calculados = lectura
        else:
            if last_entry and last_entry['tipo'] == 'partial':
                reference = last_entry['lectura']
            else:
                reference = 0
            km_calculados = lectura - reference
        km_acumulado = car['km_actual'] + km_calculados
    else:
        km_calculados = lectura - car['km_actual']
        km_acumulado = lectura

    conn.execute(
        "INSERT INTO entries (car_id, fecha, tipo, lectura, is_reset, km_calculados, km_acumulado, nota) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (car_id, fecha, tipo, lectura, 1 if is_reset else 0, km_calculados, km_acumulado, nota)
    )
    conn.execute("UPDATE cars SET km_actual = ? WHERE id = ?", (km_acumulado, car_id))
    conn.commit()
    conn.close()
    return {'km_calculados': km_calculados, 'km_acumulado': km_acumulado}, None


def preview_entry(car_id, tipo, lectura, is_reset=False):
    conn = get_db()
    car = conn.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
    if not car:
        conn.close()
        return None, "Coche no encontrado"
    car = dict(car)
    last_entry = conn.execute(
        "SELECT * FROM entries WHERE car_id = ? ORDER BY id DESC LIMIT 1",
        (car_id,)
    ).fetchone()
    conn.close()
    if tipo == 'partial':
        if is_reset:
            km_calculados = lectura
        else:
            if last_entry and last_entry['tipo'] == 'partial':
                reference = last_entry['lectura']
            else:
                reference = 0
            km_calculados = lectura - reference
        km_acumulado = car['km_actual'] + km_calculados
    else:
        km_calculados = lectura - car['km_actual']
        km_acumulado = lectura
    return {'km_calculados': round(km_calculados, 1), 'km_acumulado': round(km_acumulado, 1)}, None


def get_entries(car_id=None, limit=100, offset=0):
    conn = get_db()
    query = """
        SELECT e.*, c.modelo, c.matricula
        FROM entries e JOIN cars c ON e.car_id = c.id
    """
    params = []
    if car_id:
        query += " WHERE e.car_id = ?"
        params.append(car_id)
    query += " ORDER BY e.fecha DESC, e.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_entry(entry_id):
    conn = get_db()
    entry = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if entry:
        conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        _recalc_car_chain(conn, entry['car_id'])
        conn.commit()
    conn.close()


def add_fuel(car_id, fecha, litros, precio_litro, km_lectura, tipo_combustible, tanque_lleno, nota=''):
    conn = get_db()
    total_gasto = round(litros * precio_litro, 2)
    conn.execute(
        "INSERT INTO fuel (car_id, fecha, litros, precio_litro, total_gasto, km_lectura, tipo_combustible, tanque_lleno, nota) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (car_id, fecha, litros, precio_litro, total_gasto, km_lectura, tipo_combustible, 1 if tanque_lleno else 0, nota)
    )
    conn.commit()
    conn.close()
    return total_gasto


def get_fuel_entries(car_id=None, limit=50):
    conn = get_db()
    query = """
        SELECT f.*, c.modelo, c.matricula
        FROM fuel f JOIN cars c ON f.car_id = c.id
    """
    params = []
    if car_id:
        query += " WHERE f.car_id = ?"
        params.append(car_id)
    query += " ORDER BY f.fecha DESC, f.id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_consumption(car_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM fuel WHERE car_id = ? AND tanque_lleno = 1 ORDER BY fecha DESC, id DESC LIMIT 2",
        (car_id,)
    ).fetchall()
    conn.close()

    if len(rows) < 2:
        return None

    latest, previous = dict(rows[0]), dict(rows[1])
    if not latest.get('km_lectura') or not previous.get('km_lectura'):
        return None

    km_diff = latest['km_lectura'] - previous['km_lectura']
    if km_diff <= 0:
        return None

    conn = get_db()
    row = conn.execute(
        """SELECT SUM(litros) as total_litros FROM fuel
           WHERE car_id = ?
             AND (fecha > ? OR (fecha = ? AND id > ?))
             AND (fecha < ? OR (fecha = ? AND id <= ?))""",
        (car_id, previous['fecha'], previous['fecha'], previous['id'],
         latest['fecha'], latest['fecha'], latest['id'])
    ).fetchone()
    conn.close()

    total_litros = row['total_litros'] or 0
    if total_litros <= 0:
        return None

    conn = get_db()
    car = conn.execute("SELECT desv_km FROM cars WHERE id = ?", (car_id,)).fetchone()
    desv = car['desv_km'] if car and car['desv_km'] else 100
    conn.close()

    consumo = (total_litros / km_diff) * 100
    if desv != 100:
        consumo *= desv / 100
    return round(consumo, 2)


def get_km_mes(car_id, year=None, month=None):
    if year is None: year = datetime.now().year
    if month is None: month = datetime.now().month
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(km_calculados), 0) as total FROM entries WHERE car_id = ? AND strftime('%Y', fecha) = ? AND strftime('%m', fecha) = ?",
        (car_id, str(year), f"{month:02d}")
    ).fetchone()
    conn.close()
    return row['total']


def get_gasto_anual(car_id, year=None):
    if year is None: year = datetime.now().year
    conn = get_db()
    fuel = conn.execute(
        "SELECT COALESCE(SUM(total_gasto), 0) as total FROM fuel WHERE car_id = ? AND strftime('%Y', fecha) = ?",
        (car_id, str(year))
    ).fetchone()
    expenses = conn.execute(
        "SELECT COALESCE(SUM(coste), 0) as total FROM expenses WHERE car_id = ? AND strftime('%Y', fecha) = ?",
        (car_id, str(year))
    ).fetchone()
    maintenance = conn.execute(
        "SELECT COALESCE(SUM(coste), 0) as total FROM maintenance_records WHERE coste IS NOT NULL AND car_id = ? AND strftime('%Y', fecha) = ?",
        (car_id, str(year))
    ).fetchone()
    conn.close()
    return round(fuel['total'] + expenses['total'] + maintenance['total'], 2)


def get_gasto_mes(car_id, year=None, month=None):
    if year is None: year = datetime.now().year
    if month is None: month = datetime.now().month
    conn = get_db()
    fuel = conn.execute(
        "SELECT COALESCE(SUM(total_gasto), 0) as total FROM fuel WHERE car_id = ? AND strftime('%Y', fecha) = ? AND strftime('%m', fecha) = ?",
        (car_id, str(year), f"{month:02d}")
    ).fetchone()
    expenses = conn.execute(
        "SELECT COALESCE(SUM(coste), 0) as total FROM expenses WHERE car_id = ? AND strftime('%Y', fecha) = ? AND strftime('%m', fecha) = ?",
        (car_id, str(year), f"{month:02d}")
    ).fetchone()
    maintenance = conn.execute(
        "SELECT COALESCE(SUM(coste), 0) as total FROM maintenance_records WHERE coste IS NOT NULL AND car_id = ? AND strftime('%Y', fecha) = ? AND strftime('%m', fecha) = ?",
        (car_id, str(year), f"{month:02d}")
    ).fetchone()
    conn.close()
    return round(fuel['total'] + expenses['total'] + maintenance['total'], 2)


def get_maintenance_items(car_id=None):
    conn = get_db()
    if car_id:
        rows = conn.execute("""
            SELECT m.*, c.modelo, c.matricula, c.km_actual
            FROM maintenance_items m JOIN cars c ON m.car_id = c.id
            WHERE m.car_id = ? ORDER BY m.nombre
        """, (car_id,)).fetchall()
    else:
        rows = conn.execute(f"""
            SELECT m.*, c.modelo, c.matricula, c.km_actual
            FROM maintenance_items m JOIN cars c ON m.car_id = c.id
            WHERE {_coches_en_servicio_sql('c')}
            ORDER BY c.modelo, m.nombre
        """).fetchall()
    conn.close()
    items = []
    for r in rows:
        d = dict(r)
        d['km_restante'] = round(d['intervalo_km'] - (d['km_actual'] - d['km_ultimo']), 1)
        items.append(d)
    return items


def add_maintenance_item(car_id, nombre, intervalo_km, km_ultimo=0):
    conn = get_db()
    conn.execute(
        "INSERT INTO maintenance_items (car_id, nombre, intervalo_km, km_ultimo) VALUES (?, ?, ?, ?)",
        (car_id, nombre, intervalo_km, km_ultimo)
    )
    conn.commit()
    conn.close()


def update_maintenance_item(item_id, nombre, intervalo_km, km_ultimo):
    conn = get_db()
    conn.execute(
        "UPDATE maintenance_items SET nombre=?, intervalo_km=?, km_ultimo=? WHERE id=?",
        (nombre, intervalo_km, km_ultimo, item_id)
    )
    conn.commit()
    conn.close()


def delete_maintenance_item(item_id):
    conn = get_db()
    conn.execute("DELETE FROM maintenance_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()


# --- Maintenance Records ---

def add_maintenance_record(car_id, fecha, km, coste=None, nota=None, item_ids=None, fotos=None):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO maintenance_records (car_id, fecha, km, coste, nota) VALUES (?, ?, ?, ?, ?)",
        (car_id, fecha, km, coste, nota)
    )
    record_id = cur.lastrowid

    if item_ids:
        for item_id in item_ids:
            conn.execute(
                "INSERT INTO maintenance_record_items (record_id, item_id) VALUES (?, ?)",
                (record_id, item_id)
            )
            conn.execute(
                "UPDATE maintenance_items SET km_ultimo = ? WHERE id = ?",
                (km, item_id)
            )

    if fotos:
        for filename, tipo, data in fotos:
            conn.execute(
                "INSERT INTO maintenance_photos (record_id, filename, tipo, data) VALUES (?, ?, ?, ?)",
                (record_id, filename, tipo, data)
            )

    conn.commit()
    conn.close()
    return record_id


def get_maintenance_records(car_id, limit=50):
    conn = get_db()
    records = conn.execute("""
        SELECT r.*, GROUP_CONCAT(m.nombre, ' || ') as items_realizados
        FROM maintenance_records r
        LEFT JOIN maintenance_record_items ri ON ri.record_id = r.id
        LEFT JOIN maintenance_items m ON m.id = ri.item_id
        WHERE r.car_id = ?
        GROUP BY r.id
        ORDER BY r.fecha DESC, r.id DESC
        LIMIT ?
    """, (car_id, limit)).fetchall()
    conn.close()

    result = []
    for r in records:
        d = dict(r)
        d['fotos'] = get_maintenance_photos(r['id'])
        result.append(d)
    return result


def get_maintenance_record(record_id):
    conn = get_db()
    record = conn.execute("""
        SELECT r.*, c.matricula, c.modelo, c.pais
        FROM maintenance_records r
        JOIN cars c ON c.id = r.car_id
        WHERE r.id = ?
    """, (record_id,)).fetchone()
    if not record:
        conn.close()
        return None
    d = dict(record)
    d['items'] = conn.execute("""
        SELECT m.id, m.nombre, m.intervalo_km
        FROM maintenance_record_items ri
        JOIN maintenance_items m ON m.id = ri.item_id
        WHERE ri.record_id = ?
    """, (record_id,)).fetchall()
    d['items'] = [dict(i) for i in d['items']]
    d['fotos'] = get_maintenance_photos(record_id)
    conn.close()
    return d


def get_maintenance_photos(record_id):
    conn = get_db()
    fotos = conn.execute(
        "SELECT id, filename, tipo FROM maintenance_photos WHERE record_id = ? ORDER BY id",
        (record_id,)
    ).fetchall()
    conn.close()
    return [dict(f) for f in fotos]


def get_maintenance_photo(photo_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, record_id, filename, tipo, data FROM maintenance_photos WHERE id = ?",
        (photo_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_maintenance_record(record_id):
    conn = get_db()
    record = conn.execute("SELECT * FROM maintenance_records WHERE id = ?", (record_id,)).fetchone()
    if not record:
        conn.close()
        return False

    conn.execute("DELETE FROM maintenance_records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return True


def get_active_alerts(car_id=None):
    items = get_maintenance_items(car_id)
    try:
        umbral_rojo = float(get_setting('alerta_km_rojo', 500))
    except (ValueError, TypeError):
        umbral_rojo = 500
    try:
        umbral_amarillo = float(get_setting('alerta_km_amarillo', 3000))
    except (ValueError, TypeError):
        umbral_amarillo = 3000
    alerts = []
    for item in items:
        kr = item['km_restante']
        if kr < 0:
            alerts.append({
                'car_id': item['car_id'],
                'modelo': item['modelo'],
                'matricula': item['matricula'],
                'nombre': item['nombre'],
                'km_restante': kr,
                'status': 'red',
                'vencido': True,
            })
        elif kr <= umbral_amarillo:
            alerts.append({
                'car_id': item['car_id'],
                'modelo': item['modelo'],
                'matricula': item['matricula'],
                'nombre': item['nombre'],
                'km_restante': kr,
                'status': 'red' if kr <= umbral_rojo else 'yellow',
                'vencido': False,
            })
    return alerts


def get_daily_report(car_id=None, year=None, month=None):
    if year is None: year = datetime.now().year
    if month is None: month = datetime.now().month
    if not isinstance(year, int) or not isinstance(month, int) or not 1 <= month <= 12:
        return []

    conn = get_db()

    params_entries = [str(year), f"{month:02d}"]
    q_entries = """
        SELECT e.fecha, e.car_id, c.modelo, c.matricula, COALESCE(SUM(e.km_calculados), 0) as km
        FROM entries e JOIN cars c ON e.car_id = c.id
        WHERE strftime('%Y', e.fecha) = ? AND strftime('%m', e.fecha) = ?
    """
    q_entries += " AND " + _cond_baja_sql('c', 'e.fecha')
    if not car_id:
        q_entries += " AND c.es_prueba = 0"
    if car_id:
        q_entries += " AND e.car_id = ?"
        params_entries.append(car_id)
    q_entries += " GROUP BY e.fecha, e.car_id"
    entries_rows = conn.execute(q_entries, params_entries).fetchall()

    params_fuel = [str(year), f"{month:02d}"]
    q_fuel = """
        SELECT f.fecha, f.car_id, c.modelo, c.matricula, COALESCE(SUM(f.total_gasto), 0) as gasto
        FROM fuel f JOIN cars c ON f.car_id = c.id
        WHERE strftime('%Y', f.fecha) = ? AND strftime('%m', f.fecha) = ?
    """
    q_fuel += " AND " + _cond_baja_sql('c', 'f.fecha')
    if not car_id:
        q_fuel += " AND c.es_prueba = 0"
    if car_id:
        q_fuel += " AND f.car_id = ?"
        params_fuel.append(car_id)
    q_fuel += " GROUP BY f.fecha, f.car_id"
    fuel_rows = conn.execute(q_fuel, params_fuel).fetchall()

    params_exp = [str(year), f"{month:02d}"]
    q_exp = """
        SELECT e.fecha, e.car_id, c.modelo, c.matricula, COALESCE(SUM(e.coste), 0) as gasto
        FROM expenses e JOIN cars c ON e.car_id = c.id
        WHERE strftime('%Y', e.fecha) = ? AND strftime('%m', e.fecha) = ?
    """
    q_exp += " AND " + _cond_baja_sql('c', 'e.fecha')
    if not car_id:
        q_exp += " AND c.es_prueba = 0"
    if car_id:
        q_exp += " AND e.car_id = ?"
        params_exp.append(car_id)
    q_exp += " GROUP BY e.fecha, e.car_id"
    exp_rows = conn.execute(q_exp, params_exp).fetchall()
    conn.close()

    report = {}
    for r in entries_rows:
        d = dict(r)
        key = (d['fecha'], d['car_id'])
        report[key] = {'fecha': d['fecha'], 'modelo': d['modelo'], 'matricula': d['matricula'], 'km': d['km'], 'gasto_combustible': 0.0, 'gasto_mantenimiento': 0.0, 'total': 0.0}

    for r in fuel_rows:
        d = dict(r)
        key = (d['fecha'], d['car_id'])
        if key in report:
            report[key]['gasto_combustible'] = d['gasto']
        else:
            report[key] = {'fecha': d['fecha'], 'modelo': d['modelo'], 'matricula': d['matricula'], 'km': 0, 'gasto_combustible': d['gasto'], 'gasto_mantenimiento': 0.0, 'total': 0.0}

    for r in exp_rows:
        d = dict(r)
        key = (d['fecha'], d['car_id'])
        if key in report:
            report[key]['gasto_mantenimiento'] = d['gasto']
        else:
            report[key] = {'fecha': d['fecha'], 'modelo': d['modelo'], 'matricula': d['matricula'], 'km': 0, 'gasto_combustible': 0.0, 'gasto_mantenimiento': d['gasto'], 'total': 0.0}

    for v in report.values():
        v['total'] = round(v['gasto_combustible'] + v['gasto_mantenimiento'], 2)

    return sorted(report.values(), key=lambda x: x['fecha'], reverse=True)


def get_fuel_prices(car_id=None):
    conn = get_db()
    query = "SELECT * FROM fuel"
    params = []
    if car_id:
        query += " WHERE car_id = ?"
        params.append(car_id)
    query += " ORDER BY fecha ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Expenses ---
def add_expense(car_id, fecha, concepto, coste, categoria, km_lectura=None, nota='', fotos_data=None):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO expenses (car_id, fecha, concepto, coste, categoria, km_lectura, nota) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (car_id, fecha, concepto, coste, categoria, km_lectura, nota)
    )
    expense_id = cur.lastrowid
    if fotos_data:
        for filename, data in fotos_data:
            conn.execute(
                "INSERT INTO expense_photos (expense_id, filename, data) VALUES (?, ?, ?)",
                (expense_id, filename, data)
            )
    conn.commit()
    conn.close()


def get_expenses(car_id=None, limit=100):
    conn = get_db()
    query = """
        SELECT e.*, c.modelo, c.matricula
        FROM expenses e JOIN cars c ON e.car_id = c.id
    """
    params = []
    if car_id:
        query += " WHERE e.car_id = ?"
        params.append(car_id)
    query += " ORDER BY e.fecha DESC, e.id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    result = []
    if rows:
        ids = [r['id'] for r in rows]
        placeholders = ','.join('?' * len(ids))
        photo_rows = conn.execute(
            f"SELECT id, expense_id, filename FROM expense_photos WHERE expense_id IN ({placeholders}) ORDER BY expense_id, id",
            ids
        ).fetchall()
        photos_by_expense = {}
        for p in photo_rows:
            photos_by_expense.setdefault(p['expense_id'], []).append({'id': p['id'], 'filename': p['filename']})
    else:
        photos_by_expense = {}
    for r in rows:
        d = dict(r)
        if d.get('foto'):
            d['fotos_list'] = [f.strip() for f in d['foto'].split(',') if f.strip()]
        else:
            d['fotos_list'] = []
        d['fotos_db'] = photos_by_expense.get(d['id'], [])
        result.append(d)
    conn.close()
    return result


def get_expense_photo(photo_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, expense_id, filename, data FROM expense_photos WHERE id = ?",
        (photo_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def add_document(car_id, titulo, filename, data):
    conn = get_db()
    conn.execute(
        "INSERT INTO documents (car_id, titulo, filename, data) VALUES (?, ?, ?, ?)",
        (car_id, titulo, filename, data)
    )
    conn.commit()
    conn.close()


def get_documents(car_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, titulo, filename, created_at FROM documents WHERE car_id = ? ORDER BY id DESC",
        (car_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_document(doc_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, car_id, titulo, filename, data FROM documents WHERE id = ?",
        (doc_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_document(doc_id):
    conn = get_db()
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()


def update_expense(expense_id, fecha, concepto, coste, categoria, km_lectura=None, nota=''):
    conn = get_db()
    conn.execute(
        "UPDATE expenses SET fecha=?, concepto=?, coste=?, categoria=?, km_lectura=?, nota=? WHERE id=?",
        (fecha, concepto, coste, categoria, km_lectura, nota, expense_id)
    )
    conn.commit()
    conn.close()


def delete_expense(expense_id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    conn.close()


def add_expense_photo(expense_id, filename, data):
    conn = get_db()
    conn.execute(
        "INSERT INTO expense_photos (expense_id, filename, data) VALUES (?, ?, ?)",
        (expense_id, filename, data)
    )
    conn.commit()
    conn.close()


def delete_expense_photo(photo_id):
    conn = get_db()
    conn.execute("DELETE FROM expense_photos WHERE id=?", (photo_id,))
    conn.commit()
    conn.close()


def update_fuel(fuel_id, fecha, litros, precio_litro, km_lectura, tipo_combustible, tanque_lleno, nota=''):
    conn = get_db()
    total_gasto = round(litros * precio_litro, 2)
    conn.execute(
        "UPDATE fuel SET fecha=?, litros=?, precio_litro=?, total_gasto=?, km_lectura=?, tipo_combustible=?, tanque_lleno=?, nota=? WHERE id=?",
        (fecha, litros, precio_litro, total_gasto, km_lectura, tipo_combustible, 1 if tanque_lleno else 0, nota, fuel_id)
    )
    conn.commit()
    conn.close()
    return total_gasto


def delete_fuel(fuel_id):
    conn = get_db()
    conn.execute("DELETE FROM fuel WHERE id=?", (fuel_id,))
    conn.commit()
    conn.close()


def _recalc_car_chain(conn, car_id):
    """Recalcula la cadena de km de un coche en orden de insercion.
    Devuelve el km_actual final."""
    car = conn.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
    if not car:
        return 0
    car = dict(car)
    km_actual = car['km_inicial']
    last_entry = None
    rows = conn.execute(
        "SELECT * FROM entries WHERE car_id = ? ORDER BY id ASC",
        (car_id,)
    ).fetchall()
    for row in rows:
        row = dict(row)
        if row['tipo'] == 'partial':
            if row['is_reset']:
                km_calculados = row['lectura']
            else:
                if last_entry and last_entry['tipo'] == 'partial':
                    reference = last_entry['lectura']
                else:
                    reference = 0
                km_calculados = row['lectura'] - reference
            km_acumulado = km_actual + km_calculados
        else:
            km_calculados = row['lectura'] - km_actual
            km_acumulado = row['lectura']
        conn.execute(
            "UPDATE entries SET km_calculados=?, km_acumulado=? WHERE id=?",
            (km_calculados, km_acumulado, row['id'])
        )
        km_actual = km_acumulado
        last_entry = row
    conn.execute("UPDATE cars SET km_actual = ? WHERE id = ?", (km_actual, car_id))
    return km_actual


def update_entry(entry_id, fecha, tipo, lectura, is_reset=False, nota=''):
    conn = get_db()
    entry = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    if not entry:
        conn.close()
        return None
    entry = dict(entry)
    conn.execute(
        "UPDATE entries SET fecha=?, tipo=?, lectura=?, is_reset=?, nota=? WHERE id=?",
        (fecha, tipo, lectura, 1 if is_reset else 0, nota, entry_id)
    )

    km_actual = _recalc_car_chain(conn, entry['car_id'])
    conn.commit()
    conn.close()
    return {'km_calculados': km_actual}


def update_maintenance_record(record_id, fecha, km, coste=None, nota=None, item_ids=None):
    conn = get_db()
    conn.execute(
        "UPDATE maintenance_records SET fecha=?, km=?, coste=?, nota=? WHERE id=?",
        (fecha, km, coste, nota, record_id)
    )
    conn.execute("DELETE FROM maintenance_record_items WHERE record_id=?", (record_id,))
    if item_ids:
        for item_id in item_ids:
            conn.execute(
                "INSERT INTO maintenance_record_items (record_id, item_id) VALUES (?, ?)",
                (record_id, item_id)
            )
            conn.execute(
                "UPDATE maintenance_items SET km_ultimo = ? WHERE id = ?",
                (km, item_id)
            )
    conn.commit()
    conn.close()
    return record_id


def get_total_expenses(car_id):
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(coste), 0) as total FROM expenses WHERE car_id=?",
        (car_id,)
    ).fetchone()
    total_expenses = row['total']
    row = conn.execute(
        "SELECT COALESCE(SUM(total_gasto), 0) as total FROM fuel WHERE car_id=?",
        (car_id,)
    ).fetchone()
    total_fuel = row['total']
    row = conn.execute(
        "SELECT COALESCE(SUM(coste), 0) as total FROM maintenance_records WHERE coste IS NOT NULL AND car_id=?",
        (car_id,)
    ).fetchone()
    total_maint = row['total']
    conn.close()
    return round(total_expenses + total_fuel + total_maint, 2)


def _cond_baja_sql(alias='c', ref_fecha=None):
    """Regla contable de la baja: solo cuentan las filas con fecha <= fecha_baja.

    Sin ref_fecha (agregados de "hoy") el coche cuenta mientras no este dado de
    baja a dia de hoy. Esta regla se aplica SIEMPRE, incluso al consultar un
    coche vendido directamente con car_id: es contabilidad, no una preferencia.
    """
    if ref_fecha:
        return f"({ref_fecha} <= COALESCE({alias}.fecha_baja, '9999-12-31'))"
    return f"({alias}.fecha_baja IS NULL OR {alias}.fecha_baja > date('now'))"


def _coches_en_servicio_sql(alias='c', ref_fecha=None):
    """Condicion SQL (para AND) de los coches que cuentan en las estadisticas agregadas.

    - es_prueba = 1: nunca cuenta (coche de pruebas).
    - fecha_baja: con ref_fecha (columna de fecha de la fila) solo cuentan las filas
      con fecha <= fecha_baja, de modo que el historico anterior a la venta se
      conserva. Sin ref_fecha (agregados de "hoy") el coche cuenta mientras no
      este dado de baja a dia de hoy.
    """
    return f"{alias}.es_prueba = 0 AND {_cond_baja_sql(alias, ref_fecha)}"


def get_all_cars_usage():
    conn = get_db()
    cars = conn.execute(
        f"SELECT id, matricula, modelo, km_inicial, km_actual FROM cars c "
        f"WHERE {_coches_en_servicio_sql('c')} ORDER BY modelo"
    ).fetchall()
    conn.close()
    total_km = 0
    result = []
    for c in cars:
        km = c['km_actual'] - c['km_inicial']
        if km > 0:
            result.append({'matricula': c['matricula'], 'modelo': c['modelo'], 'km': km})
            total_km += km
    for r in result:
        r['pct'] = round((r['km'] / total_km) * 100, 1) if total_km > 0 else 0
    return result


def get_global_expense_breakdown():
    """Totales historicos. Se usa la fecha de cada fila para que los gastos
    anteriores a la baja de un coche sigan contando."""
    conn = get_db()

    def _total(tabla, col, extra=''):
        return conn.execute(
            f"SELECT COALESCE(SUM({col}), 0) as total FROM {tabla} t "
            f"WHERE t.car_id IN (SELECT id FROM cars c WHERE {_coches_en_servicio_sql('c', 't.fecha')}) {extra}"
        ).fetchone()['total']

    total_fuel = _total('fuel', 'total_gasto')
    total_exp = _total('expenses', 'coste')
    total_maint = _total('maintenance_records', 'coste', 'AND coste IS NOT NULL')
    conn.close()
    return {'fuel': round(total_fuel, 2), 'expenses': round(total_exp, 2), 'maintenance': round(total_maint, 2)}


def get_euro_per_km(car_id):
    car = get_car(car_id=car_id)
    if not car:
        return None
    km_driven = car['km_actual'] - car['km_inicial']
    if km_driven <= 0:
        return None
    total = get_total_expenses(car_id)
    return round(total / km_driven, 4)


# --- Estadisticas mensuales / informes ---
MESES_ES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']


def _coches_en_periodo_sql(alias='c', hasta=None):
    """Coches que siguen en servicio en algun momento del periodo indicado.

    'hasta' es la fecha final (YYYY-MM-DD) del periodo que se va a listar. Un
    coche vendido a mitad de periodo sigue apareciendo: sus filas posteriores a
    la baja ya quedan fuera por el filtro de fila. Sin 'hasta' (listados de
    "hoy") se exige que no este dado de baja a dia de hoy."""
    cond = [f"{alias}.es_prueba = 0"]
    if hasta:
        cond.append(f"({alias}.fecha_baja IS NULL OR {alias}.fecha_baja >= date('{hasta}'))")
    else:
        cond.append(f"({alias}.fecha_baja IS NULL OR {alias}.fecha_baja > date('now'))")
    return " AND ".join(cond)


def _fin_de_mes(year, month):
    """Ultimo dia del mes como 'YYYY-MM-DD' (para el scope por periodo)."""
    return date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def _car_scope(car_id, ref_fecha=None):
    """Devuelve (condicion_sql, params) para filtrar por coche o por todos los
    que cuentan en las estadisticas.

    Un car_id explicito NO aplica la exclusion de coche (es_prueba / ya
    vendido), para que se pueda consultar directamente su historico. La regla
    contable de fecha si se aplica siempre: los gastos posteriores a la baja no
    cuentan ni al consultar ese coche directamente."""
    if car_id:
        cond = ["car_id = ?"]
        if ref_fecha:
            # Sin alias de cars en este subquery, asi que se resuelve con un
            # subquery correlacionado sobre el propio car_id de la fila.
            cond.append(f"({ref_fecha} <= COALESCE("
                        f"(SELECT c2.fecha_baja FROM cars c2 WHERE c2.id = car_id), '9999-12-31'))")
        return " AND ".join(cond), (car_id,)
    return f"car_id IN (SELECT id FROM cars c WHERE {_coches_en_servicio_sql('c', ref_fecha)})", ()


def get_monthly_expenses(car_id=None, months=12, end_offset=0):
    """Serie de gastos mensuales (fuel + gastos + mantenimiento) para los ultimos N meses.
    end_offset=0 => termina en el mes actual; 1 => mes anterior, etc."""
    conn = get_db()
    today = date.today()
    # ancla: indice del mes final de la ventana
    anchor_y = today.year
    anchor_m = today.month
    for _ in range(end_offset):
        anchor_m -= 1
        if anchor_m == 0:
            anchor_m = 12
            anchor_y -= 1
    series = []
    for i in range(months):
        m = anchor_m - i
        y = anchor_y
        while m <= 0:
            m += 12
            y -= 1
        series.append((y, m))
    series.reverse()
    # Un scope por tabla: la fecha de cada fila debe quedar cualificada para
    # poder compararla con cars.fecha_baja dentro del subquery.
    # Ojo: los params de cada scope se intercalan con los de su subquery (SQLite
    # rellena los ? por posicion), no se concatenan todos al principio.
    scope_fuel, p_fuel = _car_scope(car_id, 'fuel.fecha')
    scope_exp, p_exp = _car_scope(car_id, 'expenses.fecha')
    scope_maint, p_maint = _car_scope(car_id, 'maintenance_records.fecha')
    result = []
    for y, m in series:
        ym = f"{m:02d}"
        row = conn.execute(
            f"""SELECT
            COALESCE((SELECT SUM(total_gasto) FROM fuel WHERE {scope_fuel} AND strftime('%Y',fecha)=? AND strftime('%m',fecha)=?),0) as fuel,
            COALESCE((SELECT SUM(coste) FROM expenses WHERE {scope_exp} AND strftime('%Y',fecha)=? AND strftime('%m',fecha)=?),0) as exp,
            COALESCE((SELECT SUM(coste) FROM maintenance_records WHERE coste IS NOT NULL AND {scope_maint} AND strftime('%Y',fecha)=? AND strftime('%m',fecha)=?),0) as maint
        """,
            p_fuel + (str(y), ym) + p_exp + (str(y), ym) + p_maint + (str(y), ym)
        ).fetchone()
        fuel, exp, maint = row['fuel'], row['exp'], row['maint']
        result.append({
            'label': f"{MESES_ES[m-1]} {str(y)[-2:]}",
            'ym': f"{y}-{m:02d}",
            'fuel': round(fuel, 2),
            'expenses': round(exp, 2),
            'maintenance': round(maint, 2),
            'total': round(fuel + exp + maint, 2),
        })
    conn.close()
    return result


def get_monthly_daily(car_id=None, year=None, month=None):
    """Gasto por dia de un mes (fuel + gastos + mantenimiento)."""
    if year is None: year = date.today().year
    if month is None: month = date.today().month
    conn = get_db()
    scope_fuel, p_fuel = _car_scope(car_id, 'fuel.fecha')
    scope_exp, p_exp = _car_scope(car_id, 'expenses.fecha')
    scope_maint, p_maint = _car_scope(car_id, 'maintenance_records.fecha')
    ym = f"{year}-{month:02d}"
    fuel_rows = conn.execute(
        f"SELECT fecha, COALESCE(SUM(total_gasto),0) t FROM fuel WHERE {scope_fuel} AND strftime('%Y-%m',fecha)=? GROUP BY fecha",
        p_fuel + (ym,)
    ).fetchall()
    exp_rows = conn.execute(
        f"SELECT fecha, COALESCE(SUM(coste),0) t FROM expenses WHERE {scope_exp} AND strftime('%Y-%m',fecha)=? GROUP BY fecha",
        p_exp + (ym,)
    ).fetchall()
    maint_rows = conn.execute(
        f"SELECT fecha, COALESCE(SUM(coste),0) t FROM maintenance_records WHERE coste IS NOT NULL AND {scope_maint} AND strftime('%Y-%m',fecha)=? GROUP BY fecha",
        p_maint + (ym,)
    ).fetchall()
    conn.close()
    days = {}
    for r in fuel_rows:
        days.setdefault(r['fecha'], {'fecha': r['fecha'], 'fuel': 0, 'expenses': 0, 'maintenance': 0})['fuel'] = r['t']
    for r in exp_rows:
        days.setdefault(r['fecha'], {'fecha': r['fecha'], 'fuel': 0, 'expenses': 0, 'maintenance': 0})['expenses'] = r['t']
    for r in maint_rows:
        days.setdefault(r['fecha'], {'fecha': r['fecha'], 'fuel': 0, 'expenses': 0, 'maintenance': 0})['maintenance'] = r['t']
    result = []
    for d in sorted(days):
        v = days[d]
        v['total'] = round(v['fuel'] + v['expenses'] + v['maintenance'], 2)
        result.append(v)
    return result


def get_monthly_by_car(year=None, month=None):
    """Resumen del mes agrupado por coche (los que siguen en servicio)."""
    if year is None: year = date.today().year
    if month is None: month = date.today().month
    conn = get_db()
    ym = f"{year}-{month:02d}"
    # Un coche vendido dentro del mes sigue listando (sus filas posteriores a la
    # baja se descartan en las sumas); si no aporta nada, se descarta luego.
    cars = conn.execute(
        f"SELECT id, matricula, modelo FROM cars c "
        f"WHERE {_coches_en_periodo_sql('c', date(year, month, 1).isoformat())} ORDER BY modelo"
    ).fetchall()
    result = []
    for c in cars:
        cid = c['id']
        row = conn.execute(
            """SELECT
                COALESCE((SELECT SUM(e.km_calculados) FROM entries e WHERE e.car_id=? AND strftime('%Y-%m',e.fecha)=? AND e.fecha <= COALESCE((SELECT c2.fecha_baja FROM cars c2 WHERE c2.id=e.car_id),'9999-12-31')),0) as km,
                COALESCE((SELECT SUM(f.litros) FROM fuel f WHERE f.car_id=? AND strftime('%Y-%m',f.fecha)=? AND f.fecha <= COALESCE((SELECT c2.fecha_baja FROM cars c2 WHERE c2.id=f.car_id),'9999-12-31')),0) as litros,
                COALESCE((SELECT COUNT(*) FROM fuel f WHERE f.car_id=? AND strftime('%Y-%m',f.fecha)=? AND f.fecha <= COALESCE((SELECT c2.fecha_baja FROM cars c2 WHERE c2.id=f.car_id),'9999-12-31')),0) as n_rep,
                COALESCE((SELECT SUM(f.total_gasto) FROM fuel f WHERE f.car_id=? AND strftime('%Y-%m',f.fecha)=? AND f.fecha <= COALESCE((SELECT c2.fecha_baja FROM cars c2 WHERE c2.id=f.car_id),'9999-12-31')),0) as fuel,
                COALESCE((SELECT SUM(e.coste) FROM expenses e WHERE e.car_id=? AND strftime('%Y-%m',e.fecha)=? AND e.fecha <= COALESCE((SELECT c2.fecha_baja FROM cars c2 WHERE c2.id=e.car_id),'9999-12-31')),0) as exp,
                COALESCE((SELECT SUM(m.coste) FROM maintenance_records m WHERE m.coste IS NOT NULL AND m.car_id=? AND strftime('%Y-%m',m.fecha)=? AND m.fecha <= COALESCE((SELECT c2.fecha_baja FROM cars c2 WHERE c2.id=m.car_id),'9999-12-31')),0) as maint
            """,
            (cid, ym, cid, ym, cid, ym, cid, ym, cid, ym, cid, ym)
        ).fetchone()
        km = row['km']
        litros = row['litros']
        n_rep = row['n_rep']
        fuel = row['fuel']
        exp = row['exp']
        maint = row['maint']
        total = round(fuel + exp + maint, 2)
        consumo = round(litros / km * 100, 2) if km > 0 and litros > 0 else None
        if consumo is not None:
            desv = conn.execute("SELECT desv_km FROM cars WHERE id = ?", (cid,)).fetchone()
            d = desv['desv_km'] if desv and desv['desv_km'] else 100
            if d != 100:
                consumo = round(consumo * d / 100, 2)
        eur_km = round(total / km, 4) if km > 0 else None
        result.append({
            'car_id': cid, 'matricula': c['matricula'], 'modelo': c['modelo'],
            'km': km, 'litros': litros, 'n_rep': n_rep,
            'fuel': round(fuel, 2), 'expenses': round(exp, 2), 'maintenance': round(maint, 2),
            'total': total, 'consumo': consumo, 'eur_km': eur_km,
        })
    result = _descartar_vendidos_sin_datos(conn, result)
    conn.close()
    return result


def _descartar_vendidos_sin_datos(conn, rows):
    """Quita las filas de coches ya dados de baja que no aportan nada al periodo.

    Un coche vendido dentro del rango debe conservar su historico anterior a la
    baja, pero si ya no aporta ninguna cifra no tiene sentido listarlo."""
    bajas = {r['id'] for r in conn.execute(
        "SELECT id FROM cars c WHERE c.fecha_baja IS NOT NULL AND c.fecha_baja <= date('now')"
    )}
    return [r for r in rows if r.get('total') or r.get('car_id') not in bajas]


def get_available_months():
    """Lista de meses (formato 'YYYY-MM') con datos en cualquier tabla, descendente."""
    conn = get_db()
    rows = conn.execute("""
        SELECT fecha FROM entries
        UNION SELECT fecha FROM fuel
        UNION SELECT fecha FROM expenses
        UNION SELECT fecha FROM maintenance_records
    """).fetchall()
    conn.close()
    months = set()
    for r in rows:
        if r['fecha'] and len(r['fecha']) >= 7:
            months.add(r['fecha'][:7])
    return sorted(months, reverse=True)


def get_report_rows(car_id=None, periods=None, group_by='car'):
    """Filas para informe estilo Excel. periods: lista de 'YYYY-MM'.
    group_by: 'car' (una fila por coche, totales del periodo) o 'car_month' (por coche y mes)."""
    if periods is None:
        periods = [date.today().strftime('%Y-%m')]
    conn = get_db()
    if car_id:
        cars = conn.execute("SELECT id, matricula, modelo FROM cars WHERE id=? ORDER BY modelo", (car_id,)).fetchall()
    else:
        # Listado por periodo: se incluye el coche si estaba en servicio al
        # inicio del rango, de modo que un coche vendido a mitad del rango no
        # hace desaparecer su historico anterior. Las filas posteriores a la baja
        # ya se descartan en las sumas.
        desde = min(date(int(p[:4]), int(p[5:7]), 1).isoformat() for p in periods if len(p) >= 7)
        cars = conn.execute(
            f"SELECT id, matricula, modelo FROM cars c "
            f"WHERE {_coches_en_periodo_sql('c', desde)} ORDER BY modelo"
        ).fetchall()

    def _sum(cid, table, col, ym, extra=''):
        # Fila a fila: solo cuentan las filas con fecha <= fecha_baja. Si el
        # coche no tiene fecha_baja, el COALESCE las deja pasar todas.
        return conn.execute(
            f"SELECT COALESCE(SUM(t.{col}),0) t FROM {table} t WHERE t.car_id=? "
            f"AND strftime('%Y-%m',t.fecha)=? "
            f"AND t.fecha <= COALESCE((SELECT c.fecha_baja FROM cars c WHERE c.id=t.car_id), '9999-12-31') "
            f"{extra}",
            (cid, ym)
        ).fetchone()['t']

    rows = []
    for c in cars:
        cid = c['id']
        if group_by == 'car_month':
            for ym in periods:
                km = _sum(cid, 'entries', 'km_calculados', ym)
                litros = _sum(cid, 'fuel', 'litros', ym)
                n_rep = conn.execute(
                    "SELECT COUNT(*) t FROM fuel t WHERE t.car_id=? AND strftime('%Y-%m',t.fecha)=? "
                    "AND t.fecha <= COALESCE((SELECT c.fecha_baja FROM cars c WHERE c.id=t.car_id),'9999-12-31')",
                    (cid, ym)
                ).fetchone()['t']
                fuel = _sum(cid, 'fuel', 'total_gasto', ym)
                exp = _sum(cid, 'expenses', 'coste', ym)
                maint = _sum(cid, 'maintenance_records', 'coste', ym, "AND coste IS NOT NULL")
                total = round(fuel + exp + maint, 2)
                consumo = round(litros / km * 100, 2) if km > 0 and litros > 0 else None
                if consumo is not None:
                    desv = conn.execute("SELECT desv_km FROM cars WHERE id = ?", (cid,)).fetchone()
                    d = desv['desv_km'] if desv and desv['desv_km'] else 100
                    if d != 100:
                        consumo = round(consumo * d / 100, 2)
                eur_km = round(total / km, 4) if km > 0 else None
                rows.append({
                    'car_id': cid, 'matricula': c['matricula'], 'modelo': c['modelo'], 'ym': ym,
                    'km': km, 'litros': litros, 'n_rep': n_rep,
                    'fuel': round(fuel, 2), 'expenses': round(exp, 2), 'maintenance': round(maint, 2),
                    'total': total, 'consumo': consumo, 'eur_km': eur_km,
                })
        else:
            km = litros = n_rep = fuel = exp = maint = 0
            for ym in periods:
                km += _sum(cid, 'entries', 'km_calculados', ym)
                litros += _sum(cid, 'fuel', 'litros', ym)
                n_rep += conn.execute(
                    "SELECT COUNT(*) t FROM fuel t WHERE t.car_id=? AND strftime('%Y-%m',t.fecha)=? "
                    "AND t.fecha <= COALESCE((SELECT c.fecha_baja FROM cars c WHERE c.id=t.car_id),'9999-12-31')",
                    (cid, ym)
                ).fetchone()['t']
                fuel += _sum(cid, 'fuel', 'total_gasto', ym)
                exp += _sum(cid, 'expenses', 'coste', ym)
                maint += _sum(cid, 'maintenance_records', 'coste', ym, "AND coste IS NOT NULL")
            total = round(fuel + exp + maint, 2)
            consumo = round(litros / km * 100, 2) if km > 0 and litros > 0 else None
            if consumo is not None:
                desv = conn.execute("SELECT desv_km FROM cars WHERE id = ?", (cid,)).fetchone()
                d = desv['desv_km'] if desv and desv['desv_km'] else 100
                if d != 100:
                    consumo = round(consumo * d / 100, 2)
            eur_km = round(total / km, 4) if km > 0 else None
            rows.append({
                'car_id': cid, 'matricula': c['matricula'], 'modelo': c['modelo'], 'ym': '+'.join(periods),
                'km': km, 'litros': litros, 'n_rep': n_rep,
                'fuel': round(fuel, 2), 'expenses': round(exp, 2), 'maintenance': round(maint, 2),
                'total': total, 'consumo': consumo, 'eur_km': eur_km,
            })
    if not car_id:
        rows = _descartar_vendidos_sin_datos(conn, rows)
    conn.close()
    return rows


def get_renewal_alerts(car_id=None):
    from datetime import date, timedelta
    conn = get_db()
    if car_id:
        rows = conn.execute(
            "SELECT * FROM cars WHERE id=?", (car_id,)
        ).fetchall()
    else:
        # Sin car_id solo avisan los coches que siguen en servicio.
        rows = conn.execute(
            f"SELECT * FROM cars c WHERE {_coches_en_servicio_sql('c')}"
        ).fetchall()
    conn.close()

    today = date.today()
    try:
        umbral_dias = int(float(get_setting('alerta_dias_renovacion', 45)))
    except (ValueError, TypeError):
        umbral_dias = 45
    alert_date = today + timedelta(days=umbral_dias)
    alerts = []
    labels = {'seguro_fecha': 'Seguro', 'itv_fecha': 'ITV', 'impuesto_fecha': 'Impuesto circulacion'}

    for car in rows:
        car = dict(car)
        for field, label in labels.items():
            val = car.get(field)
            if val:
                try:
                    fdate = date.fromisoformat(val)
                    days_left = (fdate - today).days
                    if days_left < 0:
                        alerts.append({
                            'car_id': car['id'],
                            'modelo': car['modelo'],
                            'matricula': car['matricula'],
                            'tipo': label,
                            'fecha': val,
                            'dias_restantes': days_left,
                            'status': 'red',
                        })
                    elif days_left <= umbral_dias:
                        alerts.append({
                            'car_id': car['id'],
                            'modelo': car['modelo'],
                            'matricula': car['matricula'],
                            'tipo': label,
                            'fecha': val,
                            'dias_restantes': days_left,
                            'status': 'yellow' if days_left > 7 else 'red',
                        })
                except (ValueError, TypeError):
                    pass
    return alerts


# --- Settings ---
DEFAULT_WIDGETS = [
    'km_total', 'km_mes', 'consumo', 'gasto_mes', 'gasto_anual', 'gasto_total', 'eur_km',
    'alertas_mantenimiento', 'alertas_renovacion',
]

def init_settings():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    row = conn.execute("SELECT value FROM settings WHERE key='dashboard_widgets'").fetchone()
    if not row:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ('dashboard_widgets', ','.join(DEFAULT_WIDGETS))
        )
        conn.commit()
    conn.close()


def get_dashboard_widgets():
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key='dashboard_widgets'").fetchone()
    conn.close()
    if not row:
        return DEFAULT_WIDGETS[:]
    return [w for w in row['value'].split(',') if w]


def set_dashboard_widgets(widgets):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ('dashboard_widgets', ','.join(widgets))
    )
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else default


def set_setting(key, value):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

