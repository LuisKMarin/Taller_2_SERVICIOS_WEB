from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import (
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
)

# Colombia siempre es UTC-5 (no tiene horario de verano)
COLOMBIA = timezone(timedelta(hours=-5), "COT")


def _a_hora_colombia(valor: datetime) -> str:
    """Pasa la fecha de UTC a hora de Colombia. Queda así: 2026-10-10 21:46:12-05:00"""
    if valor.tzinfo is None:  # si no trae zona horaria asumimos que es UTC
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(COLOMBIA).isoformat(sep=" ", timespec="seconds")


# tipo para que las fechas de los GET salgan en hora de Colombia
FechaColombia = Annotated[datetime, PlainSerializer(_a_hora_colombia, return_type=str)]


# --- Lo que llega por MQTT (solo se revisa la forma del mensaje) ---
# value tiene que ser un número de verdad. Si llega texto como "24.6", un booleano, NaN o infinito se rechaza
Numero = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class MagnitudMQTT(BaseModel):
    """Una magnitud del mensaje, por ejemplo {"value": 24.6, "unit": "C"}."""

    value: Numero
    unit: str = Field(strict=True, min_length=1)


class PayloadMQTT(BaseModel):
    """Estructura del mensaje que manda el sensor.

    Aquí Pydantic solo revisa que estén los campos, que los tipos sean los
    correctos y que el timestamp tenga buen formato. Si el sensor existe, la
    magnitud y la unidad se revisan después en la base de datos (crud/medicion.py).
    """

    sensor_id: str = Field(strict=True, min_length=1)
    timestamp: datetime
    measurements: dict[str, MagnitudMQTT] = Field(min_length=1)

    @field_validator("timestamp", mode="before")
    @classmethod
    def timestamp_debe_ser_texto_iso(cls, v):
        # si no ponemos esto Pydantic acepta un número como fecha
        if not isinstance(v, str):
            raise ValueError("timestamp debe ser un texto ISO 8601, ej. 2026-10-07T16:25:30Z")
        return v

    @field_validator("timestamp", mode="after")
    @classmethod
    def timestamp_con_zona_y_en_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamp debe incluir zona horaria (UTC, ej. terminar en 'Z')")
        return v.astimezone(timezone.utc)


# --- Lo que devuelve la API ---
class MedicionRead(BaseModel):
    """Una medición como la devuelven los GET."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sensor_magnitud_id: int
    magnitud: str = Field(validation_alias=AliasPath("sensor_magnitud", "magnitud"))
    unidad: str = Field(validation_alias=AliasPath("sensor_magnitud", "unidad"))
    valor: float
    timestamp_colombia: FechaColombia = Field(validation_alias="timestamp_utc")
    fecha_recepcion_colombia: FechaColombia = Field(validation_alias="fecha_recepcion")