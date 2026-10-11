from pydantic import ValidationError

from app.schemas.medicion import PayloadMQTT

BASE = {
    "sensor_id": "GAS-005",
    "timestamp": "2026-10-07T16:25:30Z",
    "measurements": {"temperature": {"value": 24.6, "unit": "C"}},
}


def caso(nombre, **cambios):
    datos = {**BASE, **cambios}
    try:
        p = PayloadMQTT.model_validate(datos)
        print(f"[OK]        {nombre}: {p.timestamp.isoformat()}")
    except ValidationError as e:
        print(f"[RECHAZADO] {nombre}: {e.errors()[0]['loc']} -> {e.errors()[0]['msg']}")


caso("payload válido")
caso("valor entero", measurements={"nh3": {"value": 12, "unit": "ppm"}})
caso("varias magnitudes", measurements={"nh3": {"value": 12.5, "unit": "ppm"}, "humidity": {"value": 50, "unit": "%"}})
caso("valor como texto", measurements={"temperature": {"value": "24.6", "unit": "C"}})
caso("valor booleano", measurements={"temperature": {"value": True, "unit": "C"}})
caso("valor nulo", measurements={"temperature": {"value": None, "unit": "C"}})
caso("unit numérica", measurements={"temperature": {"value": 24.6, "unit": 5}})
caso("sin unit", measurements={"temperature": {"value": 24.6}})
caso("measurements vacío", measurements={})
caso("timestamp basura", timestamp="ayer en la tarde")
caso("timestamp numérico", timestamp=1791390330)
caso("timestamp sin zona", timestamp="2026-10-07T16:25:30")
caso("timestamp imposible", timestamp="2026-13-45T99:99:99Z")
caso("sensor_id numérico", sensor_id=5)
try:
    PayloadMQTT.model_validate({"timestamp": "2026-10-07T16:25:30Z"})
except ValidationError as e:
    print(f"[RECHAZADO] faltan campos: {[x['loc'] for x in e.errors()]}")