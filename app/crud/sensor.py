from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sensor import Sensor


def get_sensor(db: Session, sensor_id: int) -> Sensor | None:
    """Busca un sensor por su id."""
    return db.get(Sensor, sensor_id)


def get_sensor_por_codigo(db: Session, codigo: str) -> Sensor | None:
    """Busca un sensor por su código (el sensor_id que llega por MQTT, ej. GAS-005)."""
    return db.scalar(select(Sensor).where(Sensor.codigo == codigo))


def get_sensores(db: Session, skip: int = 0, limit: int = 100) -> list[Sensor]:
    """Lista los sensores."""
    stmt = select(Sensor).order_by(Sensor.id).offset(skip).limit(limit)
    return list(db.scalars(stmt))