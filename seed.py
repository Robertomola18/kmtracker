"""Datos de ejemplo para probar KMtracker (coches y registros ficticios).

Uso:
    KMTRACKER_DB_PATH=/ruta/kmtracker.db python3 seed.py
"""
from datetime import date, timedelta

from models import (
    init_db, add_car, add_entry, add_fuel, add_expense,
    add_maintenance_record, get_maintenance_items,
)

init_db()

CARS = [
    # matricula, modelo, anyo, modo, pais, km_inicial
    ('1234ABC', 'Coche de Ejemplo', 2018, 'total', 'es', 90000),
    ('AA11BB', 'Furgoneta de Ejemplo', 2020, 'total', 'pt', 40000),
]

hoy = date.today()

for matricula, modelo, anyo, modo, pais, km in CARS:
    car_id, error = add_car(matricula, modelo, anyo, modo, pais, km_inicial=km)
    if error:
        print(f'  {matricula}: {error}')
        continue

    items = get_maintenance_items(car_id)
    add_maintenance_record(car_id, (hoy - timedelta(days=30)).isoformat(), km,
                           coste=120, nota='Revision de ejemplo',
                           item_ids=[items[0]['id']] if items else None)
    add_entry(car_id, (hoy - timedelta(days=20)).isoformat(), 'total', km + 250)
    add_entry(car_id, (hoy - timedelta(days=5)).isoformat(), 'total', km + 600)
    add_fuel(car_id, (hoy - timedelta(days=18)).isoformat(), 40, 1.55, km + 300, 'gasolina', 1)
    add_fuel(car_id, (hoy - timedelta(days=3)).isoformat(), 38, 1.57, km + 600, 'gasolina', 1)
    add_expense(car_id, (hoy - timedelta(days=10)).isoformat(), 'Seguro', 320, 'seguro')
    add_expense(car_id, (hoy - timedelta(days=2)).isoformat(), 'Lavado', 15, 'limpieza')
    print(f'  + {matricula} ({modelo}) con datos de ejemplo')

print('Datos de ejemplo creados. Arranca la app y entra en /panel.')
