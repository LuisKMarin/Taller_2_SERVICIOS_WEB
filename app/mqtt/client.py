"""Cliente MQTT: recibe los mensajes del sensor, los valida y guarda los buenos.

Qué pasa con cada mensaje (procesar_mensaje):
  1. Se lee el JSON.
  2. Pydantic revisa la estructura (schemas/medicion.py).
  3. Se revisa sensor, magnitud, unidad y rango contra la BD (crud/medicion.py).
  4. Se guarda una medición por magnitud (todas o ninguna).

Los errores de MQTT no devuelven código HTTP: se manejan aquí y quedan en el log.
"""

import json
import logging
import os

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.crud import medicion as crud_medicion
from app.database.connection import SessionLocal
from app.schemas.medicion import PayloadMQTT

load_dotenv()

logger = logging.getLogger("app.mqtt")

BROKER = os.getenv("MQTT_BROKER")
PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC = os.getenv("MQTT_TOPIC", "iot/sensors/TEST-001/data")
USERNAME = os.getenv("MQTT_USERNAME")
PASSWORD = os.getenv("MQTT_PASSWORD")
KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))
SENSOR_CODIGO = os.getenv("SENSOR_CODIGO")  # el sensor que nos asignaron


def _recortar(texto: str, maximo: int = 400) -> str:
    texto = texto.replace("\n", " ")
    return texto if len(texto) <= maximo else texto[:maximo] + "..."


def procesar_mensaje(topic: str, crudo: bytes, session_factory=SessionLocal) -> str:
    """Procesa un mensaje MQTT y devuelve 'GUARDADO' o 'RECHAZADO'.

    No lanza errores: si algo sale mal queda en el log y el mensaje se descarta.
    """
    # 1. revisar que sea un JSON
    try:
        texto = crudo.decode("utf-8")
        datos = json.loads(texto)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.warning(
            "[RECHAZADO][JSON] tópico=%s motivo=%s payload=%r",
            topic, error, crudo[:400],
        )
        return "RECHAZADO"

    logger.info("[RECEPCION] tópico=%s payload=%s", topic, _recortar(texto))

    # 2. revisar la estructura con Pydantic
    try:
        payload = PayloadMQTT.model_validate(datos)
    except ValidationError as error:
        detalle = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()
        )
        logger.warning("[RECHAZADO][ESTRUCTURA] %s", detalle)
        return "RECHAZADO"

    # 3 y 4. reglas de negocio y guardar
    try:
        with session_factory() as db:
            # solo aceptamos el sensor que nos asignaron (antes de consultar la BD)
            if SENSOR_CODIGO and payload.sensor_id != SENSOR_CODIGO:
                raise crud_medicion.MedicionRechazada(
                    f"El sensor '{payload.sensor_id}' no es el asignado "
                    f"('{SENSOR_CODIGO}')"
                )

            validadas = crud_medicion.validar_payload(db, payload)
            mediciones = crud_medicion.crear_mediciones(db, validadas, payload.timestamp)
            resumen = ", ".join(
                f"{m.sensor_magnitud.magnitud}={m.valor}" for m in mediciones
            )
            logger.info(
                "[GUARDADO] sensor=%s timestamp_utc=%s mediciones=%d (%s)",
                payload.sensor_id, payload.timestamp.isoformat(), len(mediciones), resumen,
            )
            return "GUARDADO"
    except crud_medicion.MedicionRechazada as error:
        logger.warning("[RECHAZADO][REGLA_NEGOCIO] %s", error)
        return "RECHAZADO"
    except SQLAlchemyError as error:
        logger.error("[ERROR][BASE_DE_DATOS] no se guardó el mensaje: %s", error)
        return "RECHAZADO"


# ---------- conexión MQTT ----------
def _on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code.is_failure:
        logger.error("Error de conexión MQTT: %s", reason_code)
        return
    logger.info("Conectado al broker %s:%s", BROKER, PORT)
    client.subscribe(TOPIC)  # se vuelve a suscribir cada vez que reconecta
    logger.info("Suscrito al tópico: %s", TOPIC)


def _on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    logger.warning("Desconectado del broker MQTT (%s). Reintentando...", reason_code)


def _on_message(client, userdata, message):
    procesar_mensaje(message.topic, message.payload)


def start_mqtt():
    """Inicia el cliente MQTT en un hilo aparte y lo devuelve.

    Si el broker no responde no se cae la API, solo sigue intentando conectarse.
    """
    if not BROKER:
        logger.error("Falta MQTT_BROKER en el .env: el suscriptor MQTT no se inició.")
        return None

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD or "")
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    logger.info("Conectando a %s:%s ...", BROKER, PORT)
    client.connect_async(BROKER, PORT, KEEPALIVE)
    client.loop_start()
    return client


def stop_mqtt(client) -> None:
    """Apaga el cliente MQTT."""
    if client is None:
        return
    client.disconnect()
    client.loop_stop()
    logger.info("Suscriptor MQTT detenido.")