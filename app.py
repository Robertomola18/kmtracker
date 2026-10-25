import os
import re
import json
import csv
import functools
import sys
import logging
import time
import secrets
import shutil
import tempfile
from io import BytesIO, StringIO
from pathlib import Path
from collections import defaultdict
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, send_from_directory, make_response
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('kmtracker')
from models import (
    get_all_cars, get_car, add_car, update_car, delete_car,
    add_entry, get_entries, delete_entry, update_entry,
    add_fuel, get_fuel_entries, get_consumption, delete_fuel, update_fuel,
    get_km_mes, get_gasto_mes,
    get_maintenance_items, add_maintenance_item, update_maintenance_item,
    delete_maintenance_item, get_active_alerts,
    get_daily_report, get_fuel_prices,
    add_expense, get_expenses, delete_expense, update_expense, get_expense_photo,
    add_expense_photo, delete_expense_photo,
    get_total_expenses, get_euro_per_km, get_renewal_alerts,
    get_gasto_anual, get_all_cars_usage, get_global_expense_breakdown,
    get_monthly_expenses, get_monthly_daily, get_monthly_by_car,
    get_available_months, get_report_rows,
    get_dashboard_widgets, set_dashboard_widgets, DEFAULT_WIDGETS,
    get_db, get_setting, set_setting, DB_PATH,
    add_maintenance_record, get_maintenance_records, get_maintenance_record,
    delete_maintenance_record, update_maintenance_record, get_maintenance_photo,
    update_car_foto,
    add_document, get_documents, get_document, delete_document,
)
from backup import (
    list_backups, create_backup, restore_backup, delete_backup, safe_name,
    snapshot_database, replaced_database, backup_dir as _backup_dir,
)
from datetime import date, datetime, timedelta

app = Flask(__name__)
MAX_DB_UPLOAD = 128 * 1024 * 1024


# Secret key: env var > archivo persistente
app.secret_key = os.environ.get('KMTRACKER_SECRET_KEY')
if not app.secret_key:
    KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.secret_key')
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE) as f:
            app.secret_key = f.read().strip()
    else:
        app.secret_key = os.urandom(24).hex()
        with open(KEY_FILE, 'w') as f:
            f.write(app.secret_key)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['MAX_CONTENT_LENGTH'] = MAX_DB_UPLOAD
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)


@app.before_request
def _secure_cookie_by_scheme():
    app.config['SESSION_COOKIE_SECURE'] = request.is_secure


CSRF_EXEMPT_LOGINS = ('login',)


def _csrf_required():
    token = request.form.get('_csrf')
    if not token or token != session.get('_csrf'):
        return False
    return True


@app.context_processor
def _inject_csrf():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_hex(16)
    # 'today' lo usan las plantillas para marcar los coches ya dados de baja.
    return {'csrf_token': session['_csrf'], 'today': date.today().isoformat()}


@app.before_request
def _global_csrf_check():
    if request.method != 'POST':
        return None
    # Los logins validan su propio token interno (que generan en el GET)
    if request.endpoint in CSRF_EXEMPT_LOGINS:
        return None
    if not _csrf_required():
        return _csrf_reject()
    return None


def _csrf_reject():
    return 'Error de seguridad. Intentalo de nuevo.', 403


def _csv_cell(v):
    """Neutraliza inyeccion de formulas en celdas CSV (=,+,-,@ al inicio)."""
    if v is None:
        return ''
    s = str(v)
    if s.startswith(('=', '+', '-', '@')):
        return "'" + s
    return s


def _num(value, default=None):
    """Convierte un campo de formulario a float tolerando la coma decimal.

    request.form.get(..., type=float) rechaza '25,50' (devolveria None) y el
    guardado fallaba con 'Completa todos los campos' en teclados que usan coma."""
    if value is None:
        return default
    s = str(value).strip().replace(' ', '')
    if not s:
        return default
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '.')
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


EXPENSE_CATEGORIES = (
    'seguro', 'itv', 'impuesto', 'reparacion',
    'limpieza', 'mantenimiento', 'mejoras', 'otro',
)


@app.errorhandler(413)
def _request_too_large(_error):
    flash(f'El archivo excede el tamaño máximo de {MAX_DB_UPLOAD // (1024 * 1024)} MB.', 'error')
    return redirect(url_for('admin'))


@app.after_request
def _security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    return response

UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Rate limiter simple (en memoria; por worker de gunicorn)
_login_attempts = defaultdict(list)
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW = 300

def _check_rate_limit(ip):
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < LOGIN_WINDOW]
    if len(_login_attempts[ip]) >= LOGIN_MAX_ATTEMPTS:
        return False
    return True

def _record_attempt(ip):
    _login_attempts[ip].append(time.time())

# Magic bytes de formatos de imagen permitidos
MAGIC = {
    b'\xff\xd8\xff': 'jpg',
    b'\x89PNG\r\n\x1a\n': 'png',
    b'GIF87a': 'gif',
    b'GIF89a': 'gif',
    b'RIFF': 'webp',
}


def is_allowed_image(data):
    for magic, ext in MAGIC.items():
        if data.startswith(magic):
            return ext
    return None


PDF_MAGIC = b'%PDF'


def is_allowed_document(data):
    ext = is_allowed_image(data)
    if ext and ext != 'svg':
        return 'image', ext
    if data.startswith(PDF_MAGIC):
        return 'pdf', 'pdf'
    return None, None


# --- Autenticacion ---
def login_required(route):
    @functools.wraps(route)
    def wrapper(*a, **kw):
        if not session.get('autenticado'):
            return redirect(url_for('login'))
        return route(*a, **kw)
    return wrapper


@app.route('/')
def index():
    if session.get('autenticado'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not _csrf_required():
            return render_template('login.html'), 403
        ip = request.remote_addr or 'unknown'
        if not _check_rate_limit(ip):
            logger.warning(f'Rate limit excedido desde {ip}')
            flash('Demasiados intentos. Espera 5 minutos.', 'error')
            return render_template('login.html'), 429
        pw = request.form.get('password', '')
        conn = get_db()
        row = conn.execute("SELECT value FROM settings WHERE key='password_hash'").fetchone()
        conn.close()
        if row and check_password_hash(row['value'], pw):
            session.clear()
            session.permanent = True
            session['autenticado'] = True
            return redirect(url_for('dashboard'))
        _record_attempt(ip)
        flash('Contraseña incorrecta', 'error')
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('autenticado', None)
    return redirect(url_for('login'))


def _fmt_size(size):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024:
            return f'{size:.1f} {unit}'
        size /= 1024
    return f'{size:.1f} TB'


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if request.method == 'POST':
        if not _csrf_required():
            return redirect(url_for('admin'))
        set_setting('telegram_token', request.form.get('telegram_token', '').strip())
        set_setting('telegram_allowed_ids', request.form.get('telegram_allowed_ids', '').strip())
        flash('Configuracion guardada. Reinicia el bot si cambiaste el token.', 'ok')
        return redirect(url_for('admin'))
    backups = list_backups(DB_PATH)
    for b in backups:
        b['size_h'] = _fmt_size(b['size'])
        b['mtime_h'] = datetime.fromtimestamp(b['mtime']).strftime('%Y-%m-%d %H:%M')
    return render_template(
        'admin.html',
        current_token=get_setting('telegram_token', ''),
        current_ids=get_setting('telegram_allowed_ids', ''),
        backups=backups,
        backup_dir=_backup_dir(DB_PATH),
    )


@app.route('/admin/backup')
@login_required
def admin_backup():
    tmp_dir = os.path.dirname(os.path.abspath(DB_PATH))
    fd, tmp_path = tempfile.mkstemp(prefix='.download_', suffix='.db', dir=tmp_dir)
    os.close(fd)
    try:
        snapshot_database(DB_PATH, tmp_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        logger.exception('backup download')
        flash('No se pudo preparar la descarga de la base de datos.', 'error')
        return redirect(url_for('admin'))
    response = send_file(tmp_path, as_attachment=True, download_name='kmtracker.db')

    def _cleanup_download():
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            logger.warning('No se pudo borrar la copia temporal de descarga', exc_info=True)

    response.call_on_close(_cleanup_download)
    return response


@app.route('/admin/restore', methods=['GET', 'POST'], strict_slashes=False)
@login_required
def admin_restore():
    if request.method == 'GET':
        return render_template('restore.html', backup_dir=_backup_dir(DB_PATH),
                               max_upload_mb=MAX_DB_UPLOAD // (1024 * 1024))
    if not _csrf_required():
        return redirect(url_for('admin'))
    file = request.files.get('database')
    if not file:
        flash('No se selecciono ningun archivo.', 'error')
        return redirect(url_for('admin'))
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_DB_UPLOAD:
        flash(f'El archivo excede el tamaño máximo de {MAX_DB_UPLOAD // (1024 * 1024)} MB.', 'error')
        return redirect(url_for('admin'))
    header = file.read(16)
    file.seek(0)
    if header[:16] != b'SQLite format 3\x00':
        flash('El archivo no es una base de datos SQLite valida', 'error')
        return redirect(url_for('admin'))

    tmp_dir = os.path.dirname(os.path.abspath(DB_PATH))
    fd, upload_path = tempfile.mkstemp(prefix='.restore_', suffix='.db', dir=tmp_dir)
    os.close(fd)
    try:
        file.save(upload_path)
        with replaced_database(DB_PATH, upload_path):
            from models import init_db, init_settings
            init_db()
            init_settings()
    except ValueError as exc:
        logger.warning('restore upload: %s', exc)
        flash(f'Error restaurando: {exc}', 'error')
        return redirect(url_for('admin'))
    except Exception as exc:
        logger.exception('restore upload')
        flash(f'Error restaurando: {exc}', 'error')
        return redirect(url_for('admin'))
    finally:
        try:
            if os.path.exists(upload_path):
                os.remove(upload_path)
        except OSError:
            logger.warning('No se pudo borrar el archivo temporal de restauracion', exc_info=True)
    flash('Base de datos restaurada. Backup anterior guardado como kmtracker.db.bak', 'ok')
    return redirect(url_for('admin'))


@app.route('/admin/backup-now', methods=['POST'])
@login_required
def admin_backup_now():
    if not _csrf_required():
        return redirect(url_for('admin'))
    try:
        name = create_backup(DB_PATH)
        flash(f'Copia de seguridad creada: {name}', 'ok')
    except Exception as e:
        logger.exception('backup')
        flash(f'Error creando la copia: {e}', 'error')
    return redirect(url_for('admin'))


@app.route('/admin/backup/<name>')
@login_required
def admin_backup_get(name):
    if not safe_name(name):
        flash('Backup no valido', 'error')
        return redirect(url_for('admin'))
    return send_file(os.path.join(_backup_dir(DB_PATH), name),
                     as_attachment=True, download_name=name)


@app.route('/admin/backup/<name>/restore', methods=['POST'])
@login_required
def admin_backup_restore(name):
    if not _csrf_required():
        return redirect(url_for('admin'))
    try:
        with restore_backup(DB_PATH, name):
            from models import init_db, init_settings
            init_db()
            init_settings()
        flash(f'Copia restaurada: {name}. La base anterior quedo como kmtracker.db.bak.', 'ok')
    except Exception as e:
        logger.exception('restore backup')
        flash(f'Error restaurando: {e}', 'error')
    return redirect(url_for('admin'))


@app.route('/admin/backup/<name>/delete', methods=['POST'])
@login_required
def admin_backup_delete(name):
    if not _csrf_required():
        return redirect(url_for('admin'))
    try:
        ok = delete_backup(DB_PATH, name)
        flash('Copia eliminada' if ok else 'Copia no encontrada', 'ok' if ok else 'error')
    except Exception as e:
        flash(f'Error: {e}', 'error')
    return redirect(url_for('admin'))


@app.template_global()
def plate_es(matricula):
    svg = '''<svg viewBox="0 0 22 44" class="plate-svg">
  <rect width="22" height="44" fill="#003399" rx="1"/>
  <circle cx="11" cy="14" r="6.5" fill="none" stroke="#ffcc00" stroke-width="0.35"/>
  <text transform="rotate(0,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(30,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(60,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(90,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(120,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(150,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(180,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(210,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(240,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(270,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(300,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(330,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text x="11" y="34" text-anchor="middle" fill="#fff" font-size="11" font-weight="bold" font-family="Arial,sans-serif">E</text>
</svg>'''
    return _plate_span('plate plate-es', svg, _format_plate(matricula, 'es'))


@app.template_global()
def plate_pt(matricula):
    svg = '''<svg viewBox="0 0 22 44" class="plate-svg">
  <rect width="22" height="44" fill="#003399" rx="1"/>
  <circle cx="11" cy="14" r="6.5" fill="none" stroke="#ffcc00" stroke-width="0.35"/>
  <text transform="rotate(0,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(30,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(60,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(90,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(120,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(150,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(180,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(210,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(240,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(270,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(300,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(330,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text x="11" y="34" text-anchor="middle" fill="#fff" font-size="11" font-weight="bold" font-family="Arial,sans-serif">P</text>
</svg>'''
    return _plate_span('plate plate-pt', svg, _format_plate(matricula, 'pt'))


@app.template_global()
def plate_moto(matricula, pais):
    letra = 'E' if pais == 'moto_es' else 'P'
    svg = '''<svg viewBox="0 0 22 44" class="plate-svg">
  <rect width="22" height="44" fill="#003399" rx="1"/>
  <circle cx="11" cy="14" r="6.5" fill="none" stroke="#ffcc00" stroke-width="0.35"/>
  <text transform="rotate(0,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(30,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(60,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(90,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(120,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(150,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(180,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(210,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(240,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(270,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(300,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text transform="rotate(330,11,14) translate(0,-6.5)" fill="#ffcc00" font-size="2.8" text-anchor="middle">&#9733;</text>
  <text x="11" y="34" text-anchor="middle" fill="#fff" font-size="11" font-weight="bold" font-family="Arial,sans-serif">''' + letra + '''</text>
</svg>'''
    return _plate_span('plate plate-moto', svg, _format_plate(matricula, pais))


@app.template_global()
def plate(matricula, pais):
    if pais in ('moto_es', 'moto_pt'):
        return plate_moto(matricula, pais)
    if pais == 'pt':
        return plate_pt(matricula)
    return plate_es(matricula)


def _plate_span(cls, svg, matricula):
    from markupsafe import escape
    return Markup(f'<span class="{cls}">{svg}<span class="plate-text">{escape(matricula)}</span></span>')


def _format_plate(matricula, pais):
    """Formatea la matrícula para mostrarla con separadores según el país.
    La DB guarda normalizada (sin espacios/guiones); aquí se re-insertan."""
    m = re.sub(r'[^A-Z0-9]', '', (matricula or '').upper().strip())
    if not m:
        return matricula or ''
    if pais in ('pt', 'moto_pt', 'moto_es'):
        if len(m) == 6 and m[:2].isdigit():
            return f'{m[0:2]}-{m[2:4]}-{m[4:6]}'
        if len(m) == 7 and m[:2].isdigit():
            return f'{m[0:2]}-{m[2:4]}-{m[4:7]}'
        return m
    if len(m) == 7 and m[:4].isdigit():
        return f'{m[0:4]} {m[4:7]}'
    if len(m) == 6 and m[:2].isdigit():
        return f'{m[0:2]}-{m[2:4]}-{m[4:6]}'
    return m


# --- Dashboard ---
@app.route('/panel')
@login_required
def dashboard():
    cars = get_all_cars()
    now = date.today()
    prev_m = now.month - 1 if now.month > 1 else 12
    prev_y = now.year if now.month > 1 else now.year - 1
    renewals_all = get_renewal_alerts()
    cards = []
    for c in cars:
        km_mes = get_km_mes(c['id'], now.year, now.month)
        km_mes_ant = get_km_mes(c['id'], prev_y, prev_m)
        consumo = get_consumption(c['id'])
        gasto = get_gasto_mes(c['id'], now.year, now.month)
        gasto_ant = get_gasto_mes(c['id'], prev_y, prev_m)
        gasto_anual = get_gasto_anual(c['id'], now.year)
        gasto_anual_ant = get_gasto_anual(c['id'], now.year - 1)
        total_gastos = get_total_expenses(c['id'])
        alerts = [a for a in get_active_alerts() if a['car_id'] == c['id']]
        renewals = [r for r in renewals_all if r['car_id'] == c['id']]
        eur_km = get_euro_per_km(c['id'])
        cards.append({**c, 'km_mes': km_mes, 'km_mes_ant': km_mes_ant, 'consumo': consumo, 'gasto': gasto, 'gasto_ant': gasto_ant, 'gasto_anual': gasto_anual, 'gasto_anual_ant': gasto_anual_ant, 'total_gastos': total_gastos, 'alerts': alerts, 'eur_km': eur_km, 'renewals': renewals})
    widgets = get_dashboard_widgets()
    usage = get_all_cars_usage()
    breakdown = get_global_expense_breakdown()
    chart_car = request.args.get('ccar', type=int)
    mw = request.args.get('mw', type=int) or 0
    monthly = get_monthly_expenses(car_id=chart_car, months=12, end_offset=mw)
    stats_car = request.args.get('scar', type=int)
    stats_year = request.args.get('year', type=int) or now.year
    stats_month = request.args.get('month', type=int) or now.month
    stats_daily = get_monthly_daily(car_id=stats_car, year=stats_year, month=stats_month)
    stats_by_car = get_monthly_by_car(year=stats_year, month=stats_month) if not stats_car else None
    return render_template('dashboard.html', cards=cards, widgets=widgets, usage=usage, breakdown=breakdown,
                           monthly=monthly, chart_car=chart_car, mw=mw,
                           stats_daily=stats_daily, stats_by_car=stats_by_car,
                           stats_car=stats_car, stats_year=stats_year, stats_month=stats_month)


# --- Dashboard settings ---
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        if 'widgets' in request.form:
            selected = request.form.getlist('widgets')
            set_dashboard_widgets(selected)
            flash('Dashboard actualizado', 'ok')
            return redirect(url_for('settings'))
        alerta_km_rojo = _num(request.form.get('alerta_km_rojo'))
        alerta_km_amarillo = _num(request.form.get('alerta_km_amarillo'))
        alerta_dias = request.form.get('alerta_dias_renovacion', type=int)
        if alerta_km_rojo is not None:
            set_setting('alerta_km_rojo', str(alerta_km_rojo))
        if alerta_km_amarillo is not None:
            set_setting('alerta_km_amarillo', str(alerta_km_amarillo))
        if alerta_dias is not None:
            set_setting('alerta_dias_renovacion', str(alerta_dias))
        flash('Alertas actualizadas', 'ok')
        return redirect(url_for('settings'))
    active = get_dashboard_widgets()
    alert_settings = {
        'alerta_km_rojo': get_setting('alerta_km_rojo', 500),
        'alerta_km_amarillo': get_setting('alerta_km_amarillo', 3000),
        'alerta_dias_renovacion': get_setting('alerta_dias_renovacion', 45),
    }
    return render_template('settings.html', widgets=DEFAULT_WIDGETS, active=active,
                           alert_settings=alert_settings)


# --- Car detail ---
@app.route('/coche/<matricula>')
@login_required
def car_detail(matricula):
    car = get_car(matricula=matricula)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('dashboard'))
    entries = get_entries(car['id'], limit=200)
    fuel_entries = get_fuel_entries(car['id'], limit=100)
    items = get_maintenance_items(car['id'])
    mtto_records = get_maintenance_records(car['id'], limit=50)
    consumo = get_consumption(car['id'])
    km_mes = get_km_mes(car['id'])
    gasto_mes = get_gasto_mes(car['id'])
    alerts = [a for a in get_active_alerts() if a['car_id'] == car['id']]
    expenses = get_expenses(car['id'], limit=100)
    total_expenses = get_total_expenses(car['id'])
    eur_km = get_euro_per_km(car['id'])
    renewals = [a for a in get_renewal_alerts() if a['car_id'] == car['id']]
    return render_template('car.html', car=car, entries=entries,
                           fuel_entries=fuel_entries, items=items,
                           mtto_records=mtto_records,
                           consumo=consumo, km_mes=km_mes,
                           gasto_mes=gasto_mes, alerts=alerts,
                           expenses=expenses, total_expenses=total_expenses,
                           eur_km=eur_km, renewals=renewals)


# --- Exportar CSV por seccion ---
def _car_or_redirect(matricula):
    car = get_car(matricula=matricula)
    if not car:
        flash('Coche no encontrado', 'error')
        return None
    return car


@app.route('/coche/<matricula>/export/<tipo>.csv')
@login_required
def car_export_csv(matricula, tipo):
    car = _car_or_redirect(matricula)
    if not car:
        return redirect(url_for('dashboard'))
    si = StringIO()
    writer = csv.writer(si)
    cid = car['id']
    if tipo == 'entries':
        rows = get_entries(cid, limit=100000)
        writer.writerow(['Fecha', 'Tipo', 'Lectura', 'Km', 'Acumulado', 'Reset', 'Nota'])
        for e in rows:
            writer.writerow([_csv_cell(e['fecha']), _csv_cell(e['tipo']), e['lectura'], e['km_calculados'], e['km_acumulado'],
                             'Si' if e['is_reset'] else 'No', _csv_cell(e.get('nota') or '')])
    elif tipo == 'fuel':
        rows = get_fuel_entries(cid, limit=100000)
        writer.writerow(['Fecha', 'Litros', 'Precio/L', 'Total', 'Km lectura', 'Tipo', 'Lleno', 'Nota'])
        for f in rows:
            writer.writerow([_csv_cell(f['fecha']), f['litros'], f['precio_litro'], f['total_gasto'],
                             f.get('km_lectura') or '', _csv_cell(f['tipo_combustible']),
                             'Si' if f['tanque_lleno'] else 'No', _csv_cell(f.get('nota') or '')])
    elif tipo == 'mtto':
        items = get_maintenance_items(cid)
        writer.writerow(['ITEM', 'Nombre', 'Intervalo km', 'Ultimo km', 'Restante km'])
        for it in items:
            writer.writerow(['Item', _csv_cell(it['nombre']), it['intervalo_km'], it['km_ultimo'], it['km_restante']])
        records = get_maintenance_records(cid, limit=100000)
        writer.writerow([])
        writer.writerow(['HISTORIAL', 'Fecha', 'Km', 'Coste', 'Items realizados', 'Nota'])
        for r in records:
            writer.writerow(['Registro', _csv_cell(r['fecha']), r['km'], r.get('coste') or '', _csv_cell(r.get('items_realizados') or ''), _csv_cell(r.get('nota') or '')])
    elif tipo == 'expenses':
        rows = get_expenses(cid, limit=100000)
        writer.writerow(['Fecha', 'Concepto', 'Categoria', 'Coste', 'Km', 'Nota'])
        for e in rows:
            writer.writerow([_csv_cell(e['fecha']), _csv_cell(e['concepto']), _csv_cell(e['categoria']), e['coste'],
                             e.get('km_lectura') or '', _csv_cell(e.get('nota') or '')])
    else:
        flash('Tipo de exportacion no valido', 'error')
        return redirect(url_for('car_detail', matricula=matricula))
    csv_data = '\ufeff' + si.getvalue()
    resp = make_response(csv_data)
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f"attachment; filename={matricula}_{tipo}.csv"
    return resp


@app.route('/coche/<matricula>/pdf')
@login_required
def car_pdf(matricula):
    car = _car_or_redirect(matricula)
    if not car:
        return redirect(url_for('dashboard'))
    entries = get_entries(car['id'], limit=100000)
    fuel_entries = get_fuel_entries(car['id'], limit=100000)
    items = get_maintenance_items(car['id'])
    mtto_records = get_maintenance_records(car['id'], limit=100000)
    consumo = get_consumption(car['id'])
    km_mes = get_km_mes(car['id'])
    gasto_mes = get_gasto_mes(car['id'])
    gasto_anual = get_gasto_anual(car['id'])
    gasto_anual_ant = get_gasto_anual(car['id'], date.today().year - 1)
    expenses = get_expenses(car['id'], limit=100000)
    total_expenses = get_total_expenses(car['id'])
    eur_km = get_euro_per_km(car['id'])
    renewals = [r for r in get_renewal_alerts(car_id=car['id']) if r['car_id'] == car['id']]
    renewal_fields = {'seguro_fecha': 'Seguro', 'itv_fecha': 'ITV', 'impuesto_fecha': 'Impuesto circulacion'}
    renewals_all = []
    for field, label in renewal_fields.items():
        val = car.get(field)
        if val:
            try:
                fdate = date.fromisoformat(val)
                days_left = (fdate - date.today()).days
                renewals_all.append({'tipo': label, 'fecha': val, 'dias_restantes': days_left})
            except ValueError:
                pass
    if not renewals_all:
        renewals_all = renewals
    cat_totals = {}
    for e in expenses:
        cat_totals[e['categoria']] = cat_totals.get(e['categoria'], 0) + (e['coste'] or 0)

    import base64 as _b64
    def _img_data_uri(data, filename):
        if not data:
            return None
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'jpg'
        mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
        return f"data:{mime.get(ext, 'image/jpeg')};base64,{_b64.b64encode(data).decode('ascii')}"

    car = dict(car)
    car['foto_data_uri'] = _img_data_uri(car.get('foto_data'), car.get('foto') or 'foto.jpg')
    for r in mtto_records:
        for f in r['fotos']:
            ph = get_maintenance_photo(f['id'])
            f['data_uri'] = _img_data_uri(ph.get('data') if ph else None, f['filename'])

    html = render_template('car_pdf.html', car=car, entries=entries,
                           fuel_entries=fuel_entries, items=items,
                           mtto_records=mtto_records,
                           consumo=consumo, km_mes=km_mes,
                           gasto_mes=gasto_mes, gasto_anual=gasto_anual,
                           gasto_anual_ant=gasto_anual_ant,
                           expenses=expenses, total_expenses=total_expenses,
                           eur_km=eur_km, renewals=renewals_all, cat_totals=cat_totals,
                           date=date.today().strftime('%d/%m/%Y'))
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html, base_url=request.url_root).write_pdf()
    except Exception:
        logger.exception('Error generando PDF')
        flash('Error generando PDF', 'error')
        return redirect(url_for('car_detail', matricula=matricula))
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f"attachment; filename={matricula}_informe.pdf"
    return resp


# --- Register hub ---
@app.route('/registrar')
@login_required
def registrar_hub():
    cars = get_all_cars()
    return render_template('registrar_hub.html', cars=cars)


# --- Register km entry ---
@app.route('/registrar/km', methods=['GET'])
@login_required
def registrar_km_select():
    cars = get_all_cars()
    return render_template('km_select.html', cars=cars)


@app.route('/registrar/km/<matricula>', methods=['GET', 'POST'])
@login_required
def registrar_km(matricula):
    car = get_car(matricula=matricula)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('registrar_km_select'))

    if request.method == 'POST':
        tipo = request.form.get('tipo')
        lectura = _num(request.form.get('lectura'))
        fecha = request.form.get('fecha', date.today().isoformat())
        is_reset = request.form.get('is_reset') == 'on'
        nota = request.form.get('nota', '')

        if tipo not in ('partial', 'total', 'correction') or lectura is None:
            flash('Completa todos los campos requeridos', 'error')
            return render_template('add.html', car=car, today=date.today().isoformat())

        result, error = add_entry(car['id'], fecha, tipo, lectura, is_reset, nota)
        if error:
            flash(error, 'error')
        else:
            flash(f'Registrado: +{result["km_calculados"]} km (total: {result["km_acumulado"]} km) en {car["modelo"]}', 'ok')
        return redirect(url_for('dashboard'))

    return render_template('add.html', car=car, today=date.today().isoformat())


# --- Register maintenance record ---
@app.route('/registrar/mantenimiento', methods=['GET'])
@login_required
def registrar_mantenimiento_select():
    cars = get_all_cars()
    return render_template('mantenimiento_select.html', cars=cars)


# --- Register expense ---
@app.route('/registrar/gastos', methods=['GET'])
@login_required
def registrar_gastos_select():
    cars = get_all_cars()
    return render_template('gastos_select.html', cars=cars)


# --- Register documents ---
@app.route('/registrar/documentos', methods=['GET'])
@login_required
def registrar_documentos_select():
    cars = get_all_cars()
    return render_template('documentos_select.html', cars=cars)


# --- Manage cars ---
def _parse_fecha_baja():
    """Lee y valida la fecha de baja del formulario. Devuelve (valor, error)."""
    raw = (request.form.get('fecha_baja') or '').strip()
    if not raw:
        return None, None
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        return None, 'Fecha de baja no válida (usa AAAA-MM-DD)'
    if d > date.today() + timedelta(days=365):
        return None, 'La fecha de baja no puede estar en el futuro'
    return d.isoformat(), None


def _aviso_baja(modelo, fecha_baja, renovaciones):
    """Al dar de baja un coche, avisa si tiene renovaciones con fecha posterior
    a la baja, para que se ajusten o se revisen los datos.

    'renovaciones' viene del formulario (no de la BD) porque el UPDATE de esta
    misma pantalla pone esos campos a NULL y el aviso se quedaria sin verlos."""
    if not fecha_baja or not renovaciones:
        return
    pendientes = [
        etiqueta for etiqueta, valor in (
            ('seguro', renovaciones.get('seguro_fecha')),
            ('ITV', renovaciones.get('itv_fecha')),
            ('impuesto', renovaciones.get('impuesto_fecha')),
        )
        if valor and valor > fecha_baja
    ]
    if pendientes:
        flash(
            f'Ojo: {modelo} tiene {", ".join(pendientes)} con fecha posterior a la baja '
            f'({fecha_baja}). Se seguiran contando como renovaciones pendientes.',
            'aviso'
        )


@app.route('/coches', methods=['GET', 'POST'])
@login_required
def coches():
    if request.method == 'POST':
        matricula = request.form.get('matricula', '').strip()
        modelo = request.form.get('modelo', '').strip()
        anyo = request.form.get('anyo', type=int)
        modo = request.form.get('modo')
        pais = request.form.get('pais', 'es')
        km_inicial = _num(request.form.get('km_inicial')) or 0
        es_prueba = 1 if request.form.get('es_prueba') == 'on' else 0
        motor = request.form.get('motor', '').strip()
        bastidor = request.form.get('bastidor', '').strip()
        fecha_baja, err_fecha = _parse_fecha_baja()

        if not matricula or not modelo or not anyo or modo not in ('partial', 'total'):
            flash('Completa todos los campos', 'error')
        elif err_fecha:
            flash(err_fecha, 'error')
        else:
            new_id, error = add_car(matricula, modelo, anyo, modo, pais, km_inicial, es_prueba, motor, bastidor)
            if error:
                flash(error, 'error')
            else:
                if fecha_baja:
                    conn = __import__('models').get_db()
                    conn.execute("UPDATE cars SET fecha_baja=? WHERE id=?", (fecha_baja, new_id))
                    conn.commit()
                    conn.close()
                flash(f'Coche {matricula} añadido', 'ok')
        return redirect(url_for('coches'))

    cars = get_all_cars()
    return render_template('coches.html', cars=cars)


@app.route('/coches/<int:car_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_coche(car_id):
    car = get_car(car_id=car_id)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('coches'))

    if request.method == 'POST':
        matricula = request.form.get('matricula', '').strip()
        modelo = request.form.get('modelo', '').strip()
        anyo = request.form.get('anyo', type=int)
        modo = request.form.get('modo')
        pais = request.form.get('pais', 'es')
        es_prueba = 1 if request.form.get('es_prueba') == 'on' else 0
        km_inicial = _num(request.form.get('km_inicial'))
        km_actual = _num(request.form.get('km_actual'))
        desv_km = _num(request.form.get('desv_km'))
        if desv_km is None:
            desv_km = 100
        if desv_km <= 0 or desv_km > 100:
            flash('Variacion Kilometraje debe ser un valor entre 0 y 100', 'error')
            return redirect(url_for('editar_coche', car_id=car_id))
        motor = request.form.get('motor', '').strip()
        bastidor = request.form.get('bastidor', '').strip()
        fecha_baja, err_fecha = _parse_fecha_baja()
        if err_fecha:
            flash(err_fecha, 'error')
            return redirect(url_for('editar_coche', car_id=car_id))

        ok, error = update_car(car_id, matricula, modelo, anyo, modo, pais, es_prueba, km_inicial, km_actual, motor, bastidor, desv_km)
        if error:
            flash(error, 'error')
        else:
            # Save dates
            conn = __import__('models').get_db()
            conn.execute("UPDATE cars SET seguro_fecha=?, itv_fecha=?, impuesto_fecha=?, fecha_baja=? WHERE id=?",
                         (request.form.get('seguro_fecha') or None,
                          request.form.get('itv_fecha') or None,
                          request.form.get('impuesto_fecha') or None,
                          fecha_baja,
                          car_id))
            conn.commit()
            conn.close()
            flash('Coche actualizado', 'ok')
            _aviso_baja(modelo, fecha_baja, {
                'seguro_fecha': request.form.get('seguro_fecha') or None,
                'itv_fecha': request.form.get('itv_fecha') or None,
                'impuesto_fecha': request.form.get('impuesto_fecha') or None,
            })
        return redirect(url_for('coches'))

    return render_template('coches.html', cars=get_all_cars(), edit=car)


@app.route('/coches/<int:car_id>/foto', methods=['POST'])
@login_required
def subir_foto(car_id):
    file = request.files.get('foto')
    if file:
        data = file.read(32)
        file.seek(0)
        ext = is_allowed_image(data)
    if file and ext:
        filename = f"car_{car_id}_{date.today().isoformat()}.{ext}"
        update_car_foto(car_id, filename, file.read())
        flash('Foto actualizada', 'ok')
    else:
        flash('Archivo no válido (jpg/png/gif/webp)', 'error')
    return redirect(url_for('editar_coche', car_id=car_id))


@app.route('/car_photo/<int:car_id>')
@login_required
def car_photo(car_id):
    car = get_car(car_id=car_id)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('dashboard'))
    if car.get('foto_data'):
        ext = car.get('foto', '').rsplit('.', 1)[-1].lower() if '.' in (car.get('foto') or '') else 'jpg'
        mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
        return send_file(BytesIO(car['foto_data']), mimetype=mime.get(ext, 'image/jpeg'), max_age=0)
    return redirect(url_for('static', filename=car['foto'] if car.get('foto') else ''))


@app.route('/coches/<int:car_id>/foto/borrar', methods=['POST'])
@login_required
def borrar_foto(car_id):
    car = get_car(car_id=car_id)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('coches'))
    update_car_foto(car_id, None, None)
    flash('Foto eliminada', 'ok')
    return redirect(url_for('editar_coche', car_id=car_id))


@app.route('/maintenance_photo/<int:photo_id>')
@login_required
def maintenance_photo(photo_id):
    photo = get_maintenance_photo(photo_id)
    if not photo:
        flash('Foto no encontrada', 'error')
        return redirect(url_for('dashboard'))
    if photo.get('data'):
        ext = photo['filename'].rsplit('.', 1)[-1].lower() if '.' in photo['filename'] else 'jpg'
        mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
        return send_file(BytesIO(photo['data']), mimetype=mime.get(ext, 'image/jpeg'), max_age=0)
    return redirect(url_for('static', filename='uploads/' + photo['filename']))


@app.route('/coches/<int:car_id>/eliminar', methods=['POST'])
@login_required
def eliminar_coche(car_id):
    car = delete_car(car_id)
    if car:
        flash(f'{car["modelo"]} ({car["matricula"]}) eliminado', 'ok')
    else:
        flash('Coche no encontrado', 'error')
    return redirect(url_for('coches'))


# --- Fuel ---
@app.route('/combustible', methods=['GET', 'POST'])
@login_required
def combustible():
    cars = get_all_cars()
    if request.method == 'POST':
        car_id = request.form.get('car_id', type=int)
        fecha = request.form.get('fecha', date.today().isoformat())
        litros = _num(request.form.get('litros'))
        precio_litro = _num(request.form.get('precio_litro'))
        km_lectura = _num(request.form.get('km_lectura')) or None
        tipo_comb = request.form.get('tipo_combustible')
        tanque_lleno = request.form.get('tanque_lleno') == 'on'
        nota = request.form.get('nota', '')

        if not car_id or not litros or not precio_litro or tipo_comb not in ('gasolina', 'diesel') \
                or not any(c['id'] == car_id for c in cars):
            flash('Completa todos los campos requeridos', 'error')
            return render_template('combustible.html', cars=cars)

        total = add_fuel(car_id, fecha, litros, precio_litro, km_lectura, tipo_comb, tanque_lleno, nota)
        flash(f'Repostaje registrado: {litros}L x {precio_litro}/L = {total}', 'ok')
        return redirect(url_for('combustible'))

    fuel_entries = get_fuel_entries()
    return render_template('combustible.html', cars=cars, fuel_entries=fuel_entries)


@app.route('/combustible/<int:fuel_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_repostaje(fuel_id):
    fuel = next((f for f in get_fuel_entries() if f['id'] == fuel_id), None)
    if not fuel:
        flash('Repostaje no encontrado', 'error')
        return redirect(url_for('combustible'))
    car = get_car(car_id=fuel['car_id'])

    if request.method == 'POST':
        fecha = request.form.get('fecha', date.today().isoformat())
        litros = _num(request.form.get('litros'))
        precio_litro = _num(request.form.get('precio_litro'))
        km_lectura = _num(request.form.get('km_lectura')) or None
        tipo_comb = request.form.get('tipo_combustible')
        tanque_lleno = request.form.get('tanque_lleno') == 'on'
        nota = request.form.get('nota', '')

        if not litros or not precio_litro or tipo_comb not in ('gasolina', 'diesel'):
            flash('Completa todos los campos requeridos', 'error')
            return render_template('edit_fuel.html', fuel=fuel, car=car)

        update_fuel(fuel_id, fecha, litros, precio_litro, km_lectura, tipo_comb, tanque_lleno, nota)
        flash('Repostaje actualizado', 'ok')
        return redirect(url_for('car_detail', matricula=car['matricula']))

    return render_template('edit_fuel.html', fuel=fuel, car=car)


@app.route('/combustible/precios')
@login_required
def precios():
    cars = get_all_cars()
    car_id = request.args.get('car_id', type=int)
    fuel_data = get_fuel_prices(car_id)
    return render_template('precios.html', cars=cars, fuel_data=fuel_data, selected_car=car_id)


# --- Maintenance ---
@app.route('/mantenimiento', methods=['GET', 'POST'])
@login_required
def mantenimiento():
    cars = get_all_cars()
    if request.method == 'POST':
        car_id = request.form.get('car_id', type=int)
        nombre = request.form.get('nombre', '').strip()
        intervalo_km = _num(request.form.get('intervalo_km'))
        km_ultimo = _num(request.form.get('km_ultimo')) or 0

        if not car_id or not nombre or not intervalo_km:
            flash('Completa todos los campos', 'error')
        else:
            add_maintenance_item(car_id, nombre, intervalo_km, km_ultimo)
            flash('Item de mantenimiento añadido', 'ok')
        return redirect(url_for('mantenimiento'))

    items = get_maintenance_items()
    alerts = get_active_alerts()
    return render_template('maintenance.html', cars=cars, items=items, alerts=alerts)


@app.route('/mantenimiento/<int:item_id>/editar', methods=['POST'])
@login_required
def editar_mantenimiento(item_id):
    nombre = request.form.get('nombre', '').strip()
    intervalo_km = _num(request.form.get('intervalo_km'))
    km_ultimo = _num(request.form.get('km_ultimo')) or 0
    if nombre and intervalo_km:
        update_maintenance_item(item_id, nombre, intervalo_km, km_ultimo)
    return redirect(url_for('mantenimiento'))


@app.route('/mantenimiento/<int:item_id>/eliminar', methods=['POST'])
@login_required
def eliminar_mantenimiento(item_id):
    delete_maintenance_item(item_id)
    flash('Item de mantenimiento eliminado', 'ok')
    return redirect(request.referrer or url_for('mantenimiento'))


# --- Maintenance Records ---
@app.route('/coche/<matricula>/mantenimiento/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_mantenimiento(matricula):
    car = get_car(matricula=matricula)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('dashboard'))

    items = get_maintenance_items(car_id=car['id'])

    if request.method == 'POST':
        fecha = request.form.get('fecha', date.today().isoformat())
        km = _num(request.form.get('km')) or car['km_actual']
        coste = _num(request.form.get('coste')) or None
        nota = request.form.get('nota', '').strip() or None
        item_ids = request.form.getlist('items', type=int)

        if not item_ids:
            flash('Selecciona al menos un item de mantenimiento', 'error')
            return render_template('maintenance_form.html', car=car, items=items, today=date.today().isoformat())

        fotos = []
        for key in request.files:
            file = request.files[key]
            if file and file.filename:
                data = file.read(32)
                file.seek(0)
                ext = is_allowed_image(data)
                if not ext or ext == 'svg':
                    flash('Solo se permiten imágenes (jpg/png/gif/webp)', 'error')
                    return render_template('maintenance_form.html', car=car, items=items, today=date.today().isoformat())
                filename = f"mtto_{car['id']}_{int(time.time())}_{key}.{ext}"
                tipo = 'factura' if 'factura' in key else ('piezas' if 'piezas' in key else 'general')
                fotos.append((filename, tipo, file.read()))

        record_id = add_maintenance_record(
            car['id'], fecha, km, coste, nota, item_ids, fotos
        )
        flash('Registro de mantenimiento guardado', 'ok')
        return redirect(url_for('car_detail', matricula=matricula))

    return render_template('maintenance_form.html', car=car, items=items, today=date.today().isoformat())


@app.route('/coche/<matricula>/mantenimiento/<int:record_id>/ticket')
@login_required
def ticket_mantenimiento(matricula, record_id):
    record = get_maintenance_record(record_id)
    if not record or record['matricula'] != matricula:
        flash('Registro no encontrado', 'error')
        return redirect(url_for('car_detail', matricula=matricula))
    next_items = get_maintenance_items(record['car_id'])
    car = get_car(car_id=record['car_id'])
    return render_template('maintenance_ticket.html', record=record, next_items=next_items, car=car)


@app.route('/coche/<matricula>/mantenimiento/<int:record_id>/eliminar', methods=['POST'])
@login_required
def eliminar_mantenimiento_record(matricula, record_id):
    delete_maintenance_record(record_id)
    flash('Registro de mantenimiento eliminado', 'ok')
    return redirect(url_for('car_detail', matricula=matricula))


@app.route('/coche/<matricula>/mantenimiento/<int:record_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_mantenimiento_record(matricula, record_id):
    car = get_car(matricula=matricula)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('dashboard'))
    record = get_maintenance_record(record_id)
    if not record or record['matricula'] != matricula:
        flash('Registro no encontrado', 'error')
        return redirect(url_for('car_detail', matricula=matricula))

    items = get_maintenance_items(car_id=car['id'])
    selected_ids = [i['id'] for i in record['items']]

    if request.method == 'POST':
        fecha = request.form.get('fecha', date.today().isoformat())
        km = _num(request.form.get('km')) or car['km_actual']
        coste = _num(request.form.get('coste')) or None
        nota = request.form.get('nota', '').strip() or None
        item_ids = request.form.getlist('items', type=int)

        update_maintenance_record(record_id, fecha, km, coste, nota, item_ids)
        flash('Registro de mantenimiento actualizado', 'ok')
        return redirect(url_for('car_detail', matricula=matricula))

    return render_template('maintenance_form.html', car=car, items=items,
                           today=date.today().isoformat(), record=record,
                           selected_ids=selected_ids)


# --- Expenses ---
@app.route('/coche/<matricula>/gastos', methods=['GET', 'POST'])
@login_required
def gastos(matricula):
    car = get_car(matricula=matricula)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        fecha = request.form.get('fecha', date.today().isoformat())
        concepto = request.form.get('concepto', '').strip()
        coste = _num(request.form.get('coste'))
        categoria = request.form.get('categoria')
        km_lectura = _num(request.form.get('km_lectura')) or None
        nota = request.form.get('nota', '')

        fotos_data = []
        for key in request.files:
            files = request.files.getlist(key)
            for i, file in enumerate(files):
                if file and file.filename:
                    data = file.read(32)
                    file.seek(0)
                    ext = is_allowed_image(data)
                    if not ext or ext == 'svg':
                        flash('Solo se permiten imágenes (jpg/png/gif/webp)', 'error')
                        return redirect(url_for('gastos', matricula=matricula))
                    filename = f"exp_{car['id']}_{int(time.time())}_{key}_{i}.{ext}"
                    fotos_data.append((filename, file.read()))

        if not concepto or not coste or categoria not in EXPENSE_CATEGORIES:
            flash('Completa todos los campos', 'error')
        else:
            add_expense(car['id'], fecha, concepto, coste, categoria, km_lectura, nota, fotos_data or None)
            flash('Gasto registrado', 'ok')
        return redirect(url_for('gastos', matricula=matricula))

    expenses = get_expenses(car['id'], limit=200)
    return render_template('expenses.html', car=car, expenses=expenses)


@app.route('/expense_photo/<int:photo_id>')
@login_required
def expense_photo(photo_id):
    photo = get_expense_photo(photo_id)
    if not photo:
        flash('Foto no encontrada', 'error')
        return redirect(url_for('dashboard'))
    ext = photo['filename'].rsplit('.', 1)[-1].lower() if '.' in photo['filename'] else 'jpg'
    mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
    return send_file(BytesIO(photo['data']), mimetype=mime.get(ext, 'image/jpeg'))


@app.route('/expense_photo/<int:photo_id>/delete', methods=['POST'])
@login_required
def borrar_expense_photo(photo_id):
    photo = get_expense_photo(photo_id)
    if photo:
        delete_expense_photo(photo_id)
        flash('Foto eliminada', 'ok')
    else:
        flash('Foto no encontrada', 'error')
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/coche/<matricula>/gastos/<int:expense_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_gasto(matricula, expense_id):
    car = get_car(matricula=matricula)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('dashboard'))
    expense = next((e for e in get_expenses(car['id'], limit=100000) if e['id'] == expense_id), None)
    if not expense:
        flash('Gasto no encontrado', 'error')
        return redirect(url_for('gastos', matricula=matricula))

    if request.method == 'POST':
        fecha = request.form.get('fecha', date.today().isoformat())
        concepto = request.form.get('concepto', '').strip()
        coste = _num(request.form.get('coste'))
        categoria = request.form.get('categoria')
        km_lectura = _num(request.form.get('km_lectura')) or None
        nota = request.form.get('nota', '')

        if not concepto or not coste or categoria not in EXPENSE_CATEGORIES:
            flash('Completa todos los campos', 'error')
        else:
            update_expense(expense_id, fecha, concepto, coste, categoria, km_lectura, nota)
            fotos_nuevas = []
            for key in request.files:
                files = request.files.getlist(key)
                for i, file in enumerate(files):
                    if file and file.filename:
                        data = file.read(32)
                        file.seek(0)
                        ext = is_allowed_image(data)
                        if ext and ext != 'svg':
                            filename = f"exp_{car['id']}_{int(time.time())}_{key}_{i}.{ext}"
                            fotos_nuevas.append((filename, file.read()))
            for filename, data in fotos_nuevas:
                add_expense_photo(expense_id, filename, data)
            flash('Gasto actualizado', 'ok')
            return redirect(url_for('gastos', matricula=matricula))

    return render_template('expenses.html', car=car, expenses=get_expenses(car['id'], limit=200),
                           editing=expense)


@app.route('/api/expenses/<int:expense_id>/delete', methods=['POST'])
@login_required
def api_delete_expense(expense_id):
    conn = get_db()
    row = conn.execute("SELECT car_id FROM expenses WHERE id=?", (expense_id,)).fetchone()
    conn.close()
    car = get_car(car_id=row['car_id']) if row else None
    delete_expense(expense_id)
    flash('Gasto eliminado', 'ok')
    if car:
        return redirect(url_for('gastos', matricula=car['matricula']))
    return redirect(url_for('dashboard'))


# --- Documentos por coche ---
@app.route('/coche/<matricula>/documentos')
@login_required
def documentos(matricula):
    car = get_car(matricula=matricula)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('dashboard'))
    docs = get_documents(car['id'])
    return render_template('documentos.html', car=car, docs=docs)


@app.route('/coche/<matricula>/documentos/nuevo', methods=['POST'])
@login_required
def subir_documento(matricula):
    car = get_car(matricula=matricula)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('dashboard'))

    titulo = request.form.get('titulo', '').strip()
    if not titulo:
        flash('Pon un título al documento', 'error')
        return redirect(url_for('documentos', matricula=matricula))

    file = request.files.get('archivo')
    if not file or not file.filename:
        flash('Selecciona un archivo', 'error')
        return redirect(url_for('documentos', matricula=matricula))

    data = file.read(32)
    file.seek(0)
    kind, ext = is_allowed_document(data)
    if not kind:
        flash('Solo se permiten imágenes (jpg/png/gif/webp) o PDF', 'error')
        return redirect(url_for('documentos', matricula=matricula))

    safe_name = os.path.basename(file.filename).replace('"', '').strip()[:120]
    filename = f"doc_{car['id']}_{int(time.time())}_{safe_name or ('archivo.' + ext)}"
    add_document(car['id'], titulo, filename, file.read())
    flash('Documento guardado', 'ok')
    return redirect(url_for('documentos', matricula=matricula))


@app.route('/coche/<matricula>/documentos/<int:doc_id>/eliminar', methods=['POST'])
@login_required
def eliminar_documento(matricula, doc_id):
    doc = get_document(doc_id)
    if not doc:
        flash('Documento no encontrado', 'error')
        return redirect(url_for('dashboard'))
    car = get_car(car_id=doc['car_id'])
    if not car or car['matricula'] != matricula:
        flash('Documento no encontrado', 'error')
        return redirect(url_for('dashboard'))
    delete_document(doc_id)
    flash('Documento eliminado', 'ok')
    return redirect(url_for('documentos', matricula=matricula))


@app.route('/documento/<int:doc_id>')
@login_required
def documento(doc_id):
    doc = get_document(doc_id)
    if not doc:
        flash('Documento no encontrado', 'error')
        return redirect(url_for('dashboard'))
    lower = doc['filename'].lower()
    ext = lower.rsplit('.', 1)[-1] if '.' in lower else ''
    mime = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
        'gif': 'image/gif', 'webp': 'image/webp', 'pdf': 'application/pdf',
    }
    return send_file(BytesIO(doc['data']), mimetype=mime.get(ext, 'application/octet-stream'))


# --- History ---
@app.route('/historial')
@login_required
def historial():
    car_id = request.args.get('car_id', type=int)
    entries = get_entries(car_id=car_id, limit=500)
    cars = get_all_cars()
    selected_car = next((c for c in cars if c['id'] == car_id), None) if car_id else None
    return render_template('history.html', entries=entries, cars=cars, selected_car_id=car_id,
                           selected_car=selected_car)


# --- Daily reports ---
@app.route('/informes')
@login_required
def informes():
    cars = get_all_cars()
    car_id = request.args.get('car_id', type=int)
    group_by = request.args.get('group_by', 'car')
    months = request.args.getlist('months')
    if not months:
        months = [date.today().strftime('%Y-%m')]
    periods = [m for m in months if re.match(r'^\d{4}-\d{2}$', m)]
    report = get_report_rows(car_id=car_id, periods=periods, group_by=group_by)
    available = get_available_months()
    # El selector general solo ofrece los coches en servicio. Los de prueba y los
    # dados de baja se siguen viendo en su ficha, historial y precios.
    hoy = date.today().isoformat()
    cars_selector = [
        c for c in cars
        if not c['es_prueba'] and (not c['fecha_baja'] or c['fecha_baja'] > hoy)
    ]
    # Si el coche elegido esta excluido, se mantiene en el selector para no perder el filtro.
    if car_id and not any(c['id'] == car_id for c in cars_selector):
        cars_selector = cars_selector + [c for c in cars if c['id'] == car_id]
    excluidos = ', '.join(
        f"{c['matricula']} ({c['modelo']})"
        for c in cars if c['id'] not in {x['id'] for x in cars_selector}
    )
    return render_template('informes.html', cars=cars_selector, report=report,
                           excluidos=excluidos,
                           year=date.today().year, month=date.today().month,
                           selected_car_id=car_id, group_by=group_by,
                           months=periods, available_months=available)


@app.route('/informes/export.csv')
@login_required
def informes_export():
    car_id = request.args.get('car_id', type=int)
    group_by = request.args.get('group_by', 'car')
    months = request.args.getlist('months')
    if not months:
        months = [date.today().strftime('%Y-%m')]
    periods = [m for m in months if re.match(r'^\d{4}-\d{2}$', m)]
    report = get_report_rows(car_id=car_id, periods=periods, group_by=group_by)

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Coche', 'Matricula', 'Periodo', 'Km', 'Litros', 'Repostajes',
                     'Combustible (EUR)', 'Gastos (EUR)', 'Mantenimiento (EUR)',
                     'Total (EUR)', 'Consumo L/100km', 'EUR/km'])
    for r in report:
        writer.writerow([
            _csv_cell(r['modelo']), _csv_cell(r['matricula']), r['ym'],
            r['km'], r['litros'], r['n_rep'],
            f"{r['fuel']:.2f}", f"{r['expenses']:.2f}", f"{r['maintenance']:.2f}",
            f"{r['total']:.2f}",
            f"{r['consumo']:.2f}" if r['consumo'] is not None else '',
            f"{r['eur_km']:.4f}" if r['eur_km'] is not None else '',
        ])
    csv_data = '\ufeff' + si.getvalue()
    filename = 'informe_{}.csv'.format('_'.join(periods))
    resp = make_response(csv_data)
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return resp


@app.route('/informes/ticket')
@login_required
def informe_ticket():
    car_id = request.args.get('car_id', type=int)
    year = request.args.get('year', type=int) or date.today().year
    month = request.args.get('month', type=int) or date.today().month
    report = get_daily_report(car_id=car_id, year=year, month=month)
    car = get_car(car_id=car_id) if car_id else None
    return render_template('informe_ticket.html', report=report,
                           year=year, month=month, car=car)


# --- API: delete entry ---
@app.route('/api/entries/<int:entry_id>/delete', methods=['POST'])
@login_required
def api_delete_entry(entry_id):
    conn = get_db()
    row = conn.execute("SELECT car_id FROM entries WHERE id=?", (entry_id,)).fetchone()
    conn.close()
    car = get_car(car_id=row['car_id']) if row else None
    delete_entry(entry_id)
    flash('Entrada eliminada', 'ok')
    if car:
        return redirect(url_for('car_detail', matricula=car['matricula']))
    return redirect(url_for('dashboard'))


@app.route('/coche/<matricula>/viajes/<int:entry_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_viaje(matricula, entry_id):
    car = get_car(matricula=matricula)
    if not car:
        flash('Coche no encontrado', 'error')
        return redirect(url_for('dashboard'))
    entry = next((e for e in get_entries(car['id'], limit=100000) if e['id'] == entry_id), None)
    if not entry:
        flash('Viaje no encontrado', 'error')
        return redirect(url_for('car_detail', matricula=matricula))

    if request.method == 'POST':
        fecha = request.form.get('fecha', date.today().isoformat())
        tipo = request.form.get('tipo')
        lectura = _num(request.form.get('lectura'))
        is_reset = request.form.get('is_reset') == 'on'
        nota = request.form.get('nota', '')

        if not lectura or tipo not in ('partial', 'total', 'correction'):
            flash('Datos de viaje invalidos', 'error')
            return render_template('edit_entry.html', entry=entry, car=car)

        update_entry(entry_id, fecha, tipo, lectura, is_reset, nota)
        flash('Viaje actualizado', 'ok')
        return redirect(url_for('car_detail', matricula=matricula))

    return render_template('edit_entry.html', entry=entry, car=car)


# --- API: delete fuel ---
@app.route('/api/fuel/<int:fuel_id>/delete', methods=['POST'])
@login_required
def api_delete_fuel(fuel_id):
    conn = get_db()
    row = conn.execute("SELECT car_id FROM fuel WHERE id=?", (fuel_id,)).fetchone()
    conn.close()
    car = get_car(car_id=row['car_id']) if row else None
    delete_fuel(fuel_id)
    flash('Repostaje eliminado', 'ok')
    if car:
        return redirect(url_for('car_detail', matricula=car['matricula']))
    return redirect(url_for('dashboard'))



if __name__ == '__main__':
    if os.geteuid() == 0:
        print('No ejecutar kmtracker como root', file=sys.stderr)
        sys.exit(1)
    from models import init_db, init_settings
    init_db()
    init_settings()
    # Recalcular km_actual desde entries
    conn = get_db()
    cars = conn.execute("SELECT id, km_inicial FROM cars").fetchall()
    for car in cars:
        last = conn.execute(
            "SELECT km_acumulado FROM entries WHERE car_id = ? ORDER BY id DESC LIMIT 1",
            (car['id'],)
        ).fetchone()
        km = last['km_acumulado'] if last else car['km_inicial']
        conn.execute("UPDATE cars SET km_actual = ? WHERE id = ?", (km, car['id']))
    conn.commit()
    # Password desde env var o default
    row = conn.execute("SELECT value FROM settings WHERE key='password_hash'").fetchone()
    if not row:
        password = os.environ.get('KMTRACKER_PASSWORD')
        if not password:
            raise RuntimeError('KMTRACKER_PASSWORD environment variable is required')
        pw = generate_password_hash(password)
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('password_hash', ?)", (pw,))
        conn.commit()
        print('Password hash creado.')
    conn.close()
    debug = os.environ.get('KMTRACKER_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=5050, debug=debug)

