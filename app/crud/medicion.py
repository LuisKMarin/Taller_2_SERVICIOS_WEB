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
    """El payload tiene buena estructura pero incumple una regla de negocio."""


# ---------------------------------------------------------------- escritura
def validar_payload(
    db: Session, payload: PayloadMQTT
) -> list[tuple[SensorMagnitud, Decimal]]:
    """Valida un payload ya estructurado contra el catálogo de la base de datos.

    Comprueba: el sensor existe, está activo, cada magnitud pertenece a ese
    sensor, la unidad coincide y el valor está dentro del rango permitido.
    Si UNA sola magnitud falla se rechaza todo el payload (MedicionRechazada).
    No escribe nada en la base de datos.
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
    """Guarda una medición por magnitud, todas con el mismo `timestamp_utc`.

    Se hace en una sola transacción: o se guardan todas o no se guarda ninguna.
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


# ----------------------------------------------------------------- lectura
def _mediciones_de_sensor(sensor_id: int):
    return (
        select(Medicion)
        .join(SensorMagnitud, Medicion.sensor_magnitud_id == SensorMagnitud.id)
        .where(SensorMagnitud.sensor_id == sensor_id)
        .options(joinedload(Medicion.sensor_magnitud))
    )


def get_medicion(db: Session, medicion_id: int) -> Medicion | None:
    """Busca una medición por su clave primaria."""
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
    """Histórico de un sensor, de la más reciente a la más antigua.

    Los filtros son opcionales y combinables. `limit` devuelve las últimas N.
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
    """Mediciones del instante más reciente de un sensor (una por magnitud).

    Lista vacía si el sensor todavía no tiene mediciones.
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