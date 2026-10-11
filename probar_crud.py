from pydantic import ValidationError

from app.crud import medicion as crud_medicion
from app.crud import sensor as crud_sensor
from app.crud import sensor_magnitud as crud_sensor_magnitud
from app.database.connection import SessionLocal
from app.schemas.medicion import PayloadMQTT


def payload(sensor_id="GAS-005", **medidas):
    medidas = medidas or {"nh3": {"value": 5.0, "unit": "ppm"}}
    return {
        "sensor_id": sensor_id,
        "timestamp": "2026-10-11T02:46:12Z",
        "measurements": medidas,
    }


def probar(db, nombre, datos):
    try:
        validadas = crud_medicion.validar_payload(db, PayloadMQTT.model_validate(datos))
        print(f"[ACEPTADO]  {nombre}: {[(sm.magnitud, str(v)) for sm, v in validadas]}")
    except crud_medicion.MedicionRechazada as e:
        print(f"[RECHAZADO] {nombre}: {e}")
    except ValidationError as e:
        print(f"[PYDANTIC]  {nombre}: {e.errors()[0]['msg']}")


with SessionLocal() as db:
    print("== Lecturas ==")
    s = crud_sensor.get_sensor_por_codigo(db, "GAS-005")
    print("por código:", s.id, s.codigo, "| por id:", crud_sensor.get_sensor(db, s.id).codigo)
    print("sensor 99999:", crud_sensor.get_sensor(db, 99999))
    print("total sensores:", len(crud_sensor.get_sensores(db)))
    print("magnitudes:", [m.magnitud for m in crud_sensor_magnitud.get_magnitudes_por_sensor(db, s.id)])
    print("histórico:", len(crud_medicion.get_mediciones_por_sensor(db, s.id)), "mediciones")
    print("última lectura:", crud_medicion.get_ultima_lectura(db, s.id))

    print("\n== Reglas de negocio (no escribe nada en la BD) ==")
    probar(db, "válido (3 magnitudes)", payload(
        nh3={"value": 2.01, "unit": "ppm"},
        temperature={"value": 25.27, "unit": "C"},
        humidity={"value": 84.76, "unit": "%"},
    ))
    probar(db, "sensor inexistente", payload(sensor_id="GAS-999"))
    probar(db, "unidad incorrecta", payload(nh3={"value": 5.0, "unit": "ppb"}))
    probar(db, "magnitud incorrecta", payload(pressure={"value": 5.0, "unit": "ppm"}))
    probar(db, "valor fuera de rango", payload(nh3={"value": 500.0, "unit": "ppm"}))
    probar(db, "una mala invalida todo", payload(
        nh3={"value": 5.0, "unit": "ppm"},
        temperature={"value": 25.0, "unit": "F"},
    ))
    probar(db, "valor como texto", payload(nh3={"value": "5.0", "unit": "ppm"}))