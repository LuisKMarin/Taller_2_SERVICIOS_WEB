from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sensor import Sensor


def get_sensor(db: Session, sensor_id: int) -> Sensor | None:
    """Busca un sensor por su clave primaria numérica (`id`)."""
    return db.get(Sensor, sensor_id)


def get_sensor_por_codigo(db: Session, codigo: str) -> Sensor | None:
    """Busca un sensor por su `codigo` (el `sensor_id` del payload MQTT, ej. GAS-005)."""
    return db.scalar(select(Sensor).where(Sensor.codigo == codigo))


def get_sensores(db: Session, skip: int = 0, limit: int = 100) -> list[Sensor]:
    """Lista los sensores del catálogo (solo lectura)."""
    stmt = select(Sensor).order_by(Sensor.id).offset(skip).limit(limit)
    return list(db.scalars(stmt))