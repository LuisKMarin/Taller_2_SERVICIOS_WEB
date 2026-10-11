"""Evidencias 3 a 7: mensajes MQTT inválidos que deben ser RECHAZADOS.

Ejecutar (desde la raíz del proyecto, con el entorno virtual activo):
    python probar_rechazos_mqtt.py

Cada caso pasa por app.mqtt.client.procesar_mensaje (el mismo código que usa el
suscriptor real) y se compara el número de filas de `mediciones` antes y después:
si un mensaje se rechaza correctamente, el conteo NO cambia.

Todos los casos son inválidos por diseño, así que no se inserta nada en la BD.
Genera: evidencias/03_07_rechazos_mqtt.txt
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func, select

from app.crud import sensor as crud_sensor
from app.crud import sensor_magnitud as crud_sensor_magnitud
from app.database.connection import SessionLocal
from app.models import Medicion
from app.mqtt.client import procesar_mensaje

load_dotenv()

CODIGO = os.getenv("SENSOR_CODIGO", "GAS-005")
TOPIC = os.getenv("MQTT_TOPIC", f"iot/sensors/{CODIGO}/data")
EVIDENCIAS = Path(__file__).resolve().parent / "evidencias"
EVIDENCIAS.mkdir(exist_ok=True)


class Captura(logging.Handler):
    """Guarda en una lista lo que escribe el log de app.mqtt durante cada caso."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.lineas: list[str] = []

    def emit(self, record):
        self.lineas.append(f"{record.levelname:<7} {record.getMessage()}")


def contar_mediciones() -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(Medicion))


def valor_fuera_de_rango() -> float:
    """Un valor de nh3 por encima del máximo permitido (leído del catálogo)."""
    with SessionLocal() as db:
        sensor = crud_sensor.get_sensor_por_codigo(db, CODIGO)
        sm = crud_sensor_magnitud.get_magnitud_de_sensor(db, sensor.id, "nh3")
        return float(sm.valor_maximo) + 1000.0


def main() -> None:
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def payload(**cambios):
        base = {
            "sensor_id": CODIGO,
            "timestamp": ahora,
            "measurements": {
                "nh3": {"value": 5.0, "unit": "ppm"},
                "temperature": {"value": 25.0, "unit": "C"},
                "humidity": {"value": 60.0, "unit": "%"},
            },
        }
        base.update(cambios)
        return base

    def con_medidas(**medidas):
        return payload(measurements=medidas)

    # (#prueba, nombre, mensaje (dict o bytes), archivo y función, explicación)
    casos = [
        (3, "Sensor inexistente", payload(sensor_id="GAS-999"),
         "app/crud/medicion.py -> validar_payload (get_sensor_por_codigo devuelve None)",
         "El codigo GAS-999 no existe en la tabla sensores."),
        (4, "Unidad incorrecta (nh3 en ppb, el catalogo dice ppm)",
         con_medidas(nh3={"value": 5.0, "unit": "ppb"}),
         "app/crud/medicion.py -> validar_payload (medida.unit != sm.unidad)",
         "La unidad recibida no coincide con la unidad registrada para esa magnitud."),
        (5, "Tipo de dato incorrecto: value como texto",
         con_medidas(nh3={"value": "5.0", "unit": "ppm"}),
         "app/schemas/medicion.py -> MagnitudMQTT.value (Numero con strict=True)",
         "Pydantic rechaza '5.0' (texto): value debe ser un numero JSON."),
        (5, "Tipo de dato incorrecto: value booleano",
         con_medidas(nh3={"value": True, "unit": "ppm"}),
         "app/schemas/medicion.py -> MagnitudMQTT.value (Numero con strict=True)",
         "Pydantic rechaza true: en modo estricto un booleano no es un numero."),
        (6, "Magnitud incorrecta (pressure no pertenece al sensor)",
         con_medidas(pressure={"value": 5.0, "unit": "ppm"}),
         "app/crud/medicion.py -> validar_payload (get_magnitud_de_sensor devuelve None)",
         "La magnitud no esta asociada al sensor en sensor_magnitudes."),
        (7, "Timestamp invalido: texto sin formato ISO",
         payload(timestamp="ayer en la tarde"),
         "app/schemas/medicion.py -> PayloadMQTT.timestamp",
         "No es una fecha ISO 8601 valida."),
        (7, "Timestamp invalido: fecha imposible",
         payload(timestamp="2026-13-45T99:99:99Z"),
         "app/schemas/medicion.py -> PayloadMQTT.timestamp",
         "Mes 13, dia 45 y hora 99 no existen."),
        (7, "Timestamp invalido: sin zona horaria",
         payload(timestamp="2026-10-10T16:25:30"),
         "app/schemas/medicion.py -> PayloadMQTT.timestamp_con_zona_y_en_utc",
         "El timestamp debe indicar zona horaria (UTC, termina en Z)."),
        (7, "Timestamp invalido: numerico (epoch)",
         payload(timestamp=1791390330),
         "app/schemas/medicion.py -> PayloadMQTT.timestamp_debe_ser_texto_iso",
         "Un numero no se acepta como fecha; debe ser texto ISO 8601."),
        ("extra", "Valor fuera del rango permitido",
         con_medidas(nh3={"value": valor_fuera_de_rango(), "unit": "ppm"}),
         "app/crud/medicion.py -> validar_payload (valor_minimo <= valor <= valor_maximo)",
         "El valor supera valor_maximo del catalogo."),
        ("extra", "Todo o nada: nh3 valido + temperature con unidad F",
         con_medidas(nh3={"value": 5.0, "unit": "ppm"}, temperature={"value": 25.0, "unit": "F"}),
         "app/crud/medicion.py -> validar_payload",
         "Una sola magnitud invalida rechaza todo el payload; ni siquiera nh3 (valida) se guarda."),
        ("extra", "JSON mal formado", b'{"sensor_id": "GAS-005", "timestamp": ',
         "app/mqtt/client.py -> procesar_mensaje (json.loads)",
         "El mensaje ni siquiera es JSON valido."),
    ]

    captura = Captura()
    logger = logging.getLogger("app.mqtt")
    logger.setLevel(logging.INFO)
    logger.addHandler(captura)

    salida = [
        "EVIDENCIAS #3 a #7 - Mensajes MQTT invalidos rechazados (y no almacenados)",
        f"Generado: {datetime.now():%Y-%m-%d %H:%M:%S}   Sensor: {CODIGO}   Topico: {TOPIC}",
        "Cada caso se procesa con app.mqtt.client.procesar_mensaje (la misma ruta del suscriptor real).",
        "",
    ]
    fallos = 0
    for n, (num, nombre, mensaje, donde, porque) in enumerate(casos, start=1):
        crudo = mensaje if isinstance(mensaje, bytes) else json.dumps(mensaje).encode("utf-8")
        captura.lineas.clear()
        antes = contar_mediciones()
        resultado = procesar_mensaje(TOPIC, crudo)
        despues = contar_mediciones()
        bien = resultado == "RECHAZADO" and antes == despues
        fallos += 0 if bien else 1

        salida += [
            f"--- Caso {n} (prueba #{num}): {nombre} ---",
            f"Entrada            : {crudo.decode('utf-8')}",
            f"Resultado          : {resultado}",
            f"Mediciones en BD   : antes={antes} despues={despues} -> "
            + ("NO se almaceno nada (correcto)" if bien else "ATENCION: algo no salio como se esperaba"),
            "Registro en el log :",
            *[f"    {linea}" for linea in captura.lineas],
            f"Archivo y funcion  : {donde}",
            f"Explicacion        : {porque}",
            "",
        ]

    salida.append(
        "RESUMEN: todos los casos fueron rechazados y la tabla mediciones no cambio."
        if fallos == 0
        else f"RESUMEN: {fallos} caso(s) NO se comportaron como se esperaba. Revisa arriba."
    )
    texto = "\n".join(salida) + "\n"
    (EVIDENCIAS / "03_07_rechazos_mqtt.txt").write_text(texto, encoding="utf-8")
    print(texto)
    print(f"Guardado en {EVIDENCIAS / '03_07_rechazos_mqtt.txt'}")


if __name__ == "__main__":
    main()