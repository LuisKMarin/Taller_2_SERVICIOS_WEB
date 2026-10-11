from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sensor_magnitud import SensorMagnitud


def get_sensor_magnitud(db: Session, sensor_magnitud_id: int) -> SensorMagnitud | None:
    """Busca una magnitud de sensor por su id."""
    return db.get(SensorMagnitud, sensor_magnitud_id)


def get_magnitudes_por_sensor(db: Session, sensor_id: int) -> list[SensorMagnitud]:
    """Lista las magnitudes que mide un sensor."""
    stmt = (
        select(SensorMagnitud)
        .where(SensorMagnitud.sensor_id == sensor_id)
        .order_by(SensorMagnitud.id)
    )
    return list(db.scalars(stmt))


def get_magnitud_de_sensor(
    db: Session, sensor_id: int, magnitud: str
) -> SensorMagnitud | None:
    """Busca la magnitud con ese nombre dentro de un sensor."""
    stmt = select(SensorMagnitud).where(
        SensorMagnitud.sensor_id == sensor_id,
        SensorMagnitud.magnitud == magnitud,
    )
    return db.scalar(stmt)