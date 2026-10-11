from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.crud import sensor as crud_sensor
from app.crud import sensor_magnitud as crud_sensor_magnitud
from app.models.medicion import Medicion
from app.models.sensor_magnitud import SensorMagnitud
from app.schemas.medicion import PayloadMQTT


class MedicionRechazada(Exception):
    """Se usa cuando el mensaje está bien armado pero no cumple alguna regla (sensor, unidad, rango...)."""


# ---------- escritura ----------
def validar_payload(
    db: Session, payload: PayloadMQTT
) -> list[tuple[SensorMagnitud, Decimal]]:
    """Revisa un mensaje contra lo que hay en la base de datos.

    Mira que el sensor exista y esté activo, que cada magnitud sea de ese sensor,
    que la unidad coincida y que el valor esté dentro del rango.
    Si una sola magnitud falla se rechaza todo el mensaje.
    Esta función no guarda nada.
    """
    sensor = crud_sensor.get_sensor_por_codigo(db, payload.sensor_id)
    if sensor is None:
        raise MedicionRechazada(f"Sensor inexistente: '{payload.sensor_id}'")
    if not sensor.activo:
        raise MedicionRechazada(f"Sensor inactivo: '{sensor.codigo}'")

    validadas: list[tuple[SensorMagnitud, Decimal]] = []
    for nombre, medida in payload.measurements.items():
        sm = crud_sensor_magnitud.get_magnitud_de_sensor(db, sensor.id, nombre)
        if sm is None:
            raise MedicionRechazada(
                f"La magnitud '{nombre}' no pertenece al sensor '{sensor.codigo}'"
            )
        if medida.unit != sm.unidad:
            raise MedicionRechazada(
                f"Unidad incorrecta para '{nombre}': llegó '{medida.unit}', "
                f"se esperaba '{sm.unidad}'"
            )
        valor = Decimal(str(medida.value))
        if not (sm.valor_minimo <= valor <= sm.valor_maximo):
            raise MedicionRechazada(
                f"Valor fuera de rango para '{nombre}': {valor} "
                f"(permitido {sm.valor_minimo} a {sm.valor_maximo})"
            )
        validadas.append((sm, valor))
    return validadas


def crear_mediciones(
    db: Session,
    validadas: list[tuple[SensorMagnitud, Decimal]],
    timestamp_utc: datetime,
) -> list[Medicion]:
    """Guarda una medición por cada magnitud, todas con el mismo timestamp_utc.

    Es una sola transacción: se guardan todas o no se guarda ninguna.
    """
    mediciones = [
        Medicion(sensor_magnitud_id=sm.id, valor=valor, timestamp_utc=timestamp_utc)
        for sm, valor in validadas
    ]
    try:
        db.add_all(mediciones)
        db.commit()
    except Exception:
        db.rollback()
        raise
    for m in mediciones:
        db.refresh(m)
    return mediciones


# ---------- lectura ----------
def _mediciones_de_sensor(sensor_id: int):
    return (
        select(Medicion)
        .join(SensorMagnitud, Medicion.sensor_magnitud_id == SensorMagnitud.id)
        .where(SensorMagnitud.sensor_id == sensor_id)
        .options(joinedload(Medicion.sensor_magnitud))
    )


def get_medicion(db: Session, medicion_id: int) -> Medicion | None:
    """Busca una medición por su id."""
    return db.scalar(
        select(Medicion)
        .where(Medicion.id == medicion_id)
        .options(joinedload(Medicion.sensor_magnitud))
    )


def get_mediciones_por_sensor(
    db: Session,
    sensor_id: int,
    magnitud: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    limit: int | None = None,
) -> list[Medicion]:
    """Historial de un sensor, de la más nueva a la más vieja.

    Los filtros son opcionales y se pueden combinar. limit trae las últimas N.
    """
    stmt = _mediciones_de_sensor(sensor_id)
    if magnitud is not None:
        stmt = stmt.where(SensorMagnitud.magnitud == magnitud)
    if desde is not None:
        stmt = stmt.where(Medicion.timestamp_utc >= desde)
    if hasta is not None:
        stmt = stmt.where(Medicion.timestamp_utc <= hasta)
    stmt = stmt.order_by(Medicion.timestamp_utc.desc(), Medicion.id.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def get_ultima_lectura(db: Session, sensor_id: int) -> list[Medicion]:
    """Trae las mediciones del momento más reciente de un sensor (una por magnitud).

    Si el sensor no tiene mediciones devuelve una lista vacía.
    """
    ultimo = db.scalar(
        select(func.max(Medicion.timestamp_utc))
        .join(SensorMagnitud, Medicion.sensor_magnitud_id == SensorMagnitud.id)
        .where(SensorMagnitud.sensor_id == sensor_id)
    )
    if ultimo is None:
        return []
    stmt = (
        _mediciones_de_sensor(sensor_id)
        .where(Medicion.timestamp_utc == ultimo)
        .order_by(Medicion.id)
    )
    return list(db.scalars(stmt))