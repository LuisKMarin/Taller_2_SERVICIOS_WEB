"""Suscriptor MQTT: recibe, valida y guarda las mediciones del sensor asignado.

Flujo de cada mensaje (procesar_mensaje):
  1. Decodificar el JSON.
  2. Validar la estructura con Pydantic (schemas/medicion.py).
  3. Validar sensor, magnitud, unidad y rango contra la BD (crud/medicion.py).
  4. Guardar una medición por magnitud (todo o nada).

Los errores MQTT no devuelven códigos HTTP: se manejan aquí y quedan en el log.
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
SENSOR_CODIGO = os.getenv("SENSOR_CODIGO")  # sensor asignado al grupo


def _recortar(texto: str, maximo: int = 400) -> str:
    texto = texto.replace("\n", " ")
    return texto if len(texto) <= maximo else texto[:maximo] + "..."


def procesar_mensaje(topic: str, crudo: bytes, session_factory=SessionLocal) -> str:
    """Procesa un mensaje MQTT completo y devuelve 'GUARDADO' o 'RECHAZADO'.

    Nunca lanza excepciones: cualquier problema se registra en el log y el
    mensaje se descarta sin guardar nada.
    """
    # 1. JSON válido
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

    # 2. Estructura (Pydantic)
    try:
        payload = PayloadMQTT.model_validate(datos)
    except ValidationError as error:
        detalle = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()
        )
        logger.warning("[RECHAZADO][ESTRUCTURA] %s", detalle)
        return "RECHAZADO"

    # 3 y 4. Reglas de negocio (ORM) y guardado
    try:
        with session_factory() as db:
            validadas = crud_medicion.validar_payload(db, payload)

            if SENSOR_CODIGO and payload.sensor_id != SENSOR_CODIGO:
                raise crud_medicion.MedicionRechazada(
                    f"El sensor '{payload.sensor_id}' no es el asignado "
                    f"('{SENSOR_CODIGO}')"
                )

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


# ------------------------------------------------------------ conexión MQTT
def _on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code.is_failure:
        logger.error("Error de conexión MQTT: %s", reason_code)
        return
    logger.info("Conectado al broker %s:%s", BROKER, PORT)
    client.subscribe(TOPIC)  # se repite en cada reconexión
    logger.info("Suscrito al tópico: %s", TOPIC)


def _on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    logger.warning("Desconectado del broker MQTT (%s). Reintentando...", reason_code)


def _on_message(client, userdata, message):
    procesar_mensaje(message.topic, message.payload)


def start_mqtt():
    """Inicia el suscriptor en un hilo aparte y devuelve el cliente.

    No bloquea ni rompe la API si el broker no responde: reintenta solo.
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
    """Detiene el suscriptor de forma ordenada."""
    if client is None:
        return
    client.disconnect()
    client.loop_stop()
    logger.info("Suscriptor MQTT detenido.")