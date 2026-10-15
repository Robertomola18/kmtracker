"""Coches excluidos de las estadisticas: es_prueba (pruebas) y fecha_baja (vendido).

Reglas que se comprueban aqui:
- es_prueba = 1 nunca cuenta en ningun agregado.
- Los gastos con fecha <= fecha_baja siguen contando (historico contable previo
  a la venta); los posteriores no.
- Una consulta con car_id explicito no filtra: el historico de un coche vendido
  debe poder consultarse directamente.
- En los listados por periodo el coche vendido aparece mientras aporte algo, y
  desaparece cuando ya no aporta nada.
"""
import os
from datetime import date, timedelta

import pytest


MATRICULAS = ('1111AAA', '2222BBB', '3333CCC', '4444DDD')


@pytest.fixture
def parque(km_db_path):
    """Cuatro coches: activo, de prueba, vendido y con baja programada.

    La BD es de sesion, asi que se limpia antes y despues para poder repetir la
    suite sin chocar con la restriccion UNIQUE de matricula.

    La baja se ancla al ultimo dia del mes anterior para que las fechas que
    derivan en gastos_venta (baja -/+ 10 d) caigan siempre en meses distintos,
    que es lo que asumen los informes por periodo. Con (hoy - 30 d) el mes
    dependia de cuando se ejecutara la suite: entre los dias 11 y 20 del mes el
    "pre" y el "post" caian en el mismo mes y 3 tests fallaban."""
    import models
    conn = models.get_db()
    conn.execute("DELETE FROM cars WHERE matricula IN (%s)" % ','.join('?' * len(MATRICULAS)),
                 MATRICULAS)
    hoy = date.today()
    baja = (hoy.replace(day=1) - timedelta(days=1)).isoformat()
    fut = (hoy + timedelta(days=30)).isoformat()
    # Todos con seguro proximo: get_renewal_alerts solo avisa de coches que
    # tienen alguna renovacion guardada, asi que sin esto no habria nada que avisar.
    seguro = (hoy + timedelta(days=10)).isoformat()
    for mat, modelo, prueba, f_baja, km in [
        ('1111AAA', 'Activo', 0, None, 100000),
        ('2222BBB', 'Prueba', 1, None, 5000),
        ('3333CCC', 'Vendido', 0, baja, 60000),
        ('4444DDD', 'BajaFutura', 0, fut, 80000),
    ]:
        conn.execute(
            "INSERT INTO cars (matricula, modelo, anyo, modo, km_inicial, km_actual,"
            " es_prueba, fecha_baja, seguro_fecha) VALUES (?, ?, 2020, 'total', 0, ?, ?, ?, ?)",
            (mat, modelo, km, prueba, f_baja, seguro))
    conn.commit()
    ids = {r['matricula']: r['id'] for r in conn.execute("SELECT id, matricula FROM cars")}
    conn.close()
    yield {'ids': ids, 'baja': baja}
    conn = models.get_db()
    conn.execute("DELETE FROM cars WHERE matricula IN (%s)" % ','.join('?' * len(MATRICULAS)),
                 MATRICULAS)
    conn.commit()
    conn.close()


def _fuel(conn, car_id, fecha, gasto):
    conn.execute(
        "INSERT INTO fuel (car_id, fecha, litros, precio_litro, total_gasto,"
        " km_lectura, tipo_combustible, tanque_lleno) VALUES (?, ?, 50, 2, ?, 1000, 'diesel', 1)",
        (car_id, fecha.isoformat(), gasto))


def _mantenimiento(conn, car_id, fecha, coste):
    conn.execute(
        "INSERT INTO maintenance_records (car_id, fecha, km, coste) VALUES (?, ?, 0, ?)",
        (car_id, fecha.isoformat(), coste))


# --- Esquema y valor por defecto ------------------------------------------

def test_fecha_baja_existe_y_por_defecto_es_nula(km_db_path):
    import models
    conn = models.get_db()
    cols = {r['name'] for r in conn.execute("PRAGMA table_info(cars)")}
    conn.close()
    assert 'fecha_baja' in cols


def test_init_db_es_idempotente_con_fecha_baja(km):
    import models
    models.init_db()
    models.init_db()
    conn = models.get_db()
    n = len(conn.execute("PRAGMA table_info(cars)").fetchall())
    conn.close()
    assert n == 18, 'la tabla cars debe seguir teniendo 18 columnas'


def test_coche_nuevo_arranca_sin_fecha_baja(km):
    import models
    car_id, err = models.add_car('7777ZZZ', 'Nuevo', 2024, 'total', 'es')
    assert not err
    assert models.get_car(car_id=car_id)['fecha_baja'] is None


# --- Coches de prueba ------------------------------------------------------

def test_coche_de_prueba_no_aparece_en_uso_de_flota(parque):
    import models
    modelos = {r['modelo'] for r in models.get_all_cars_usage()}
    assert 'Prueba' not in modelos
    assert modelos == {'Activo', 'BajaFutura'}


def test_coche_de_prueba_no_aparece_en_informes(parque):
    import models
    modelos = {r['modelo'] for r in models.get_report_rows()}
    assert 'Prueba' not in modelos


# --- Coches vendidos: el historico se conserva ---------------------------

@pytest.fixture
def gastos_venta(km, parque):
    """Gasto del coche vendido 10 dias antes y 10 dias despues de la baja."""
    import models
    baja = date.fromisoformat(parque['baja'])
    conn = models.get_db()
    _fuel(conn, parque['ids']['3333CCC'], baja - timedelta(days=10), 100.0)
    _fuel(conn, parque['ids']['3333CCC'], baja + timedelta(days=10), 999.0)
    _mantenimiento(conn, parque['ids']['3333CCC'], baja - timedelta(days=10), 300.0)
    _mantenimiento(conn, parque['ids']['3333CCC'], baja + timedelta(days=10), 777.0)
    conn.commit()
    conn.close()
    return {'pre': baja - timedelta(days=10), 'post': baja + timedelta(days=10)}


def test_el_gasto_posterior_a_la_baja_no_cuenta(gastos_venta):
    import models
    t = models.get_global_expense_breakdown()
    assert t['fuel'] == 100.0, 'solo debe contar el repostaje previo a la baja'
    assert t['maintenance'] == 300.0, 'solo debe contar el mantenimiento previo'


def test_la_serie_mensual_conserva_el_mes_previo_a_la_baja(gastos_venta):
    import models
    serie = {s['ym']: s for s in models.get_monthly_expenses(months=14)}
    pre = gastos_venta['pre'].strftime('%Y-%m')
    post = gastos_venta['post'].strftime('%Y-%m')
    assert serie[pre]['fuel'] == 100.0
    assert serie[pre]['maintenance'] == 300.0
    # el mes posterior existe pero sin los importes del coche vendido
    assert 999.0 not in [s['fuel'] for s in serie.values()]
    assert 777.0 not in [s['maintenance'] for s in serie.values()]
    assert serie[post]['fuel'] == 0.0


def test_el_informe_diario_ignora_el_dia_posterior_a_la_baja(gastos_venta):
    import models
    rows = models.get_daily_report(year=gastos_venta['pre'].year, month=gastos_venta['pre'].month)
    fechas = [r['fecha'] for r in rows if r['modelo'] == 'Vendido']
    assert fechas == [gastos_venta['pre'].isoformat()]


def test_el_coche_vendido_sale_de_los_agregados_actuales(parque):
    import models
    assert 'Vendido' not in {r['modelo'] for r in models.get_all_cars_usage()}
    assert 'Vendido' not in {r['matricula'] for r in models.get_renewal_alerts()}
    assert '3333CCC' not in {i['matricula'] for i in models.get_maintenance_items()}


def test_las_alertas_se_silencian_solo_si_la_baja_es_actual(parque):
    import models
    # Sin car_id solo avisan los que siguen en servicio: ni prueba ni vendido.
    assert {r['matricula'] for r in models.get_renewal_alerts()} == {'1111AAA', '4444DDD'}
    # Con car_id explicito si avisa: se puede consultar un coche concreto.
    assert '3333CCC' in {r['matricula'] for r in
                         models.get_renewal_alerts(car_id=parque['ids']['3333CCC'])}
    # Una baja en el futuro no silencia las alertas.
    assert '4444DDD' in {r['matricula'] for r in models.get_renewal_alerts()}


def test_un_car_id_explicito_no_filtra(gastos_venta, parque):
    """Consultar un coche vendido directamente debe devolver su historico."""
    import models
    serie = models.get_monthly_expenses(car_id=parque['ids']['3333CCC'], months=14)
    assert sum(s['fuel'] for s in serie) == 100.0
    rows = models.get_report_rows(car_id=parque['ids']['3333CCC'])
    assert len(rows) == 1 and rows[0]['modelo'] == 'Vendido'


def test_la_serie_mensual_con_car_id_coincide_con_la_de_todos(gastos_venta, parque):
    """Regresion: al fijar un coche, los parametros SQL de cada subquery deben
    intercalarse con los de su tabla. Si se concatenan al principio, cada
    subquery recibe anio/mes equivocados y la serie sale vacia."""
    import models
    cid = parque['ids']['3333CCC']
    uno = models.get_monthly_expenses(car_id=cid, months=14)
    todos = models.get_monthly_expenses(months=14)
    assert uno == todos, 'un coche no puede cambiar el resultado de la serie'


def test_el_diario_con_car_id_explicito_ignora_la_baja(gastos_venta, parque):
    import models
    cid = parque['ids']['3333CCC']
    diario = models.get_monthly_daily(car_id=cid, year=gastos_venta['pre'].year,
                                      month=gastos_venta['pre'].month)
    assert [d['fecha'] for d in diario] == [gastos_venta['pre'].isoformat()]
    assert diario[0]['total'] == 400.0


# --- Informes por periodo --------------------------------------------------

def test_el_vendido_aparece_en_un_informe_anterior_a_su_baja(gastos_venta):
    import models
    pre = gastos_venta['pre'].strftime('%Y-%m')
    filas = {r['modelo']: r for r in models.get_report_rows(periods=[pre])}
    assert 'Vendido' in filas, 'el historico previo a la venta debe seguir visible'
    assert filas['Vendido']['total'] == 400.0  # 100 combustible + 300 mantenimiento


def test_el_vendido_desaparece_de_un_informe_posterior_a_su_baja(gastos_venta):
    import models
    post = gastos_venta['post'].strftime('%Y-%m')
    assert 'Vendido' not in {r['modelo'] for r in models.get_report_rows(periods=[post])}


def test_un_rango_que_cruza_la_venta_conserva_el_historico(gastos_venta):
    """Pedir los dos meses a la vez no debe hacer desaparecer el gasto previo."""
    import models
    pre = gastos_venta['pre'].strftime('%Y-%m')
    post = gastos_venta['post'].strftime('%Y-%m')
    filas = {r['ym']: r['total'] for r in
             models.get_report_rows(periods=[pre, post], group_by='car_month')
             if r['modelo'] == 'Vendido'}
    assert filas == {pre: 400.0}, 'solo el mes previo aporta datos'


def test_el_desglose_mensual_por_coche_respeta_la_baja(gastos_venta):
    import models
    pre, post = gastos_venta['pre'], gastos_venta['post']
    antes = {r['modelo']: r for r in models.get_monthly_by_car(year=pre.year, month=pre.month)}
    assert antes['Vendido']['total'] == 400.0
    assert antes['Vendido']['n_rep'] == 1, 'los repostajes posteriores no cuentan'
    despues = {r['modelo'] for r in models.get_monthly_by_car(year=post.year, month=post.month)}
    assert 'Vendido' not in despues


def test_el_coche_con_baja_programada_sigue_contando(parque):
    """Una baja en el futuro no excluye al coche de nada."""
    import models
    assert '4444DDD' in {r['matricula'] for r in models.get_renewal_alerts()}
    assert 'BajaFutura' in {r['modelo'] for r in models.get_all_cars_usage()}


# --- Interfaz --------------------------------------------------------------

def test_el_coche_baja_se_puede_guardar_desde_la_web(km, logged_client):
    import models
    csrf = _csrf(logged_client, '/coches')
    resp = logged_client.post('/coches', data={
        'matricula': '8888HHH', 'modelo': 'VendidoPorWeb', 'anyo': '2022', 'modo': 'total',
        'pais': 'es', 'km_inicial': '0', '_csrf': csrf,
    }, follow_redirects=True)
    assert resp.status_code == 200
    car_id, err = _last_car('8888HHH')
    assert not err
    f = (date.today() - timedelta(days=1)).isoformat()
    resp = logged_client.post(f'/coches/{car_id}/editar', data={
        'matricula': '8888HHH', 'modelo': 'VendidoPorWeb', 'anyo': '2022', 'modo': 'total',
        'pais': 'es', 'km_inicial': '0', 'km_actual': '0', 'desv_km': '100',
        'fecha_baja': f, '_csrf': _csrf(logged_client, f'/coches/{car_id}/editar'),
    }, follow_redirects=True)
    assert models.get_car(car_id=car_id)['fecha_baja'] == f


def test_una_fecha_de_baja_invalida_se_rechaza(km, logged_client):
    csrf = _csrf(logged_client, '/coches')
    resp = logged_client.post('/coches', data={
        'matricula': '9999ZZZ', 'modelo': 'Malo', 'anyo': '2022', 'modo': 'total',
        'pais': 'es', 'km_inicial': '0', 'fecha_baja': '31-12-2020', '_csrf': csrf,
    }, follow_redirects=True)
    assert 'Fecha de baja no v' in resp.get_data(as_text=True)
    assert _last_car('9999ZZZ')[1], 'no debe crearse el coche'


def test_una_fecha_de_baja_futura_se_rechaza(km, logged_client):
    csrf = _csrf(logged_client, '/coches')
    resp = logged_client.post('/coches', data={
        'matricula': '9999YYY', 'modelo': 'Malo', 'anyo': '2022', 'modo': 'total',
        'pais': 'es', 'km_inicial': '0', 'fecha_baja': '2099-01-01', '_csrf': csrf,
    }, follow_redirects=True)
    assert 'no puede estar en el futuro' in resp.get_data(as_text=True)
    assert _last_car('9999YYY')[1]


def test_avisa_si_hay_renovaciones_posteriores_a_la_baja(km, logged_client):
    car_id, _ = _crear('1111QQQ', 'ConRenovacion', es_prueba=0)
    baja = (date.today() - timedelta(days=5)).isoformat()
    futura = (date.today() + timedelta(days=30)).isoformat()
    resp = logged_client.post(f'/coches/{car_id}/editar', data={
        'matricula': '1111QQQ', 'modelo': 'ConRenovacion', 'anyo': '2020', 'modo': 'total',
        'pais': 'es', 'km_inicial': '0', 'km_actual': '0', 'desv_km': '100',
        'fecha_baja': baja, 'seguro_fecha': futura,
        '_csrf': _csrf(logged_client, f'/coches/{car_id}/editar'),
    }, follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert 'Ojo:' in html and 'seguro' in html


def test_no_avisa_si_no_hay_renovaciones_posteriores(km, logged_client):
    car_id, _ = _crear('2222RRR', 'SinRenovacion')
    baja = (date.today() - timedelta(days=5)).isoformat()
    resp = logged_client.post(f'/coches/{car_id}/editar', data={
        'matricula': '2222RRR', 'modelo': 'SinRenovacion', 'anyo': '2020', 'modo': 'total',
        'pais': 'es', 'km_inicial': '0', 'km_actual': '0', 'desv_km': '100',
        'fecha_baja': baja, 'seguro_fecha': '2020-01-01',
        '_csrf': _csrf(logged_client, f'/coches/{car_id}/editar'),
    }, follow_redirects=True)
    assert 'Ojo:' not in resp.get_data(as_text=True)


def test_el_selector_de_informes_oculta_los_excluidos(km, logged_client):
    _, _ = _crear('3000AAA', 'ActivoWeb')
    _, _ = _crear('3000BBB', 'PruebaWeb', es_prueba=1)
    _, _ = _crear('3000CCC', 'VendidoWeb',
                  fecha_baja=(date.today() - timedelta(days=5)).isoformat())
    html = logged_client.get('/informes').get_data(as_text=True)
    selector = html.split('<select name="car_id">')[1].split('</select>')[0]
    assert '3000AAA' in selector
    assert '3000BBB' not in selector, 'los coches de prueba no se ofrecen'
    assert '3000CCC' not in selector, 'los coches vendidos no se ofrecen'
    assert 'No aparecen en el selector' in html, 'se explica por que faltan'


def test_la_ficha_marca_los_coches_excluidos(km, logged_client):
    baja = (date.today() - timedelta(days=5)).isoformat()
    _, _ = _crear('4000CCC', 'VendidoFicha', fecha_baja=baja)
    _, _ = _crear('4000BBB', 'PruebaFicha', es_prueba=1)
    html = logged_client.get('/coches').get_data(as_text=True)
    assert 'Vendido' in html and baja in html
    assert 'Excluido de estadisticas' in html
    assert 'car-excluido' in html


# --- Utilidades ------------------------------------------------------------

def _csrf(client, url):
    import re
    html = client.get(url).get_data(as_text=True)
    m = re.search(r'name="_csrf" value="([^"]+)"', html)
    assert m, f'no se encontro csrf en {url}'
    return m.group(1)


def _crear(matricula, modelo, es_prueba=0, fecha_baja=None):
    import models
    conn = models.get_db()
    conn.execute(
        "INSERT INTO cars (matricula, modelo, anyo, modo, km_inicial, km_actual,"
        " es_prueba, fecha_baja) VALUES (?, ?, 2020, 'total', 0, 0, ?, ?)",
        (matricula, modelo, es_prueba, fecha_baja))
    conn.commit()
    car_id = conn.execute("SELECT id FROM cars WHERE matricula=?", (matricula,)).fetchone()['id']
    conn.close()
    return car_id, None


def _last_car(matricula):
    import models
    conn = models.get_db()
    row = conn.execute("SELECT id FROM cars WHERE matricula=?", (matricula,)).fetchone()
    conn.close()
    return (row['id'] if row else None), (row is None)