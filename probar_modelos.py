from sqlalchemy import select

from app.database.connection import SessionLocal
from app.models import Sensor

with SessionLocal() as db:
    sensor = db.scalar(select(Sensor).where(Sensor.codigo == "GAS-005"))
    if sensor is None:
        print("No existe el sensor GAS-005")
    else:
        print(f"Sensor: {sensor.id} | {sensor.codigo} | {sensor.nombre}")
        print(f"Categoría: {sensor.categoria} | Activo: {sensor.activo}")
        for m in sensor.magnitudes:
            print(
                f"  - {m.magnitud} ({m.unidad}) "
                f"rango {m.valor_minimo} a {m.valor_maximo}"
            )