from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class SensorMagnitud(Base):
    """Tabla sensor_magnitudes. Solo la leemos, la dejó el profe."""

    __tablename__ = "sensor_magnitudes"
    __table_args__ = (
        UniqueConstraint("sensor_id", "magnitud"),
        CheckConstraint("valor_minimo < valor_maximo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[int] = mapped_column(
        ForeignKey("sensores.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    magnitud: Mapped[str] = mapped_column(String(50), nullable=False)
    unidad: Mapped[str] = mapped_column(String(20), nullable=False)
    valor_minimo: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    valor_maximo: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    sensor: Mapped["Sensor"] = relationship(back_populates="magnitudes")
    mediciones: Mapped[list["Medicion"]] = relationship(
        back_populates="sensor_magnitud"
    )