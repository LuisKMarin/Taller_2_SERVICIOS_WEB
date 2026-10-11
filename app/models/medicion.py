from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Medicion(Base):
    """Tabla `mediciones` (aquí sí se insertan los datos válidos recibidos por MQTT)."""

    __tablename__ = "mediciones"
    __table_args__ = (
        Index("idx_mediciones_sensor_magnitud", "sensor_magnitud_id"),
        Index("idx_mediciones_timestamp_utc", "timestamp_utc"),
        Index(
            "idx_mediciones_magnitud_timestamp",
            "sensor_magnitud_id",
            "timestamp_utc",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sensor_magnitud_id: Mapped[int] = mapped_column(
        ForeignKey("sensor_magnitudes.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    timestamp_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fecha_recepcion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sensor_magnitud: Mapped["SensorMagnitud"] = relationship(
        back_populates="mediciones"
    )