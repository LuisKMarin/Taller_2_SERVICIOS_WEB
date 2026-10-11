from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

# value: número JSON (int o float). Rechaza textos ("24.6"), booleanos, NaN e infinito.
Numero = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class MagnitudMQTT(BaseModel):
    """Una magnitud dentro del payload: {"value": 24.6, "unit": "C"}."""

    value: Numero
    unit: str = Field(strict=True, min_length=1)


class PayloadMQTT(BaseModel):
    """Estructura completa del mensaje que publica el sensor por MQTT.

    Pydantic valida SOLO la forma: campos obligatorios, tipos y formato del
    timestamp. Que el sensor exista, la magnitud pertenezca a él y la unidad
    coincida se valida después contra la base de datos (crud/ + mqtt/client.py).
    """

    sensor_id: str = Field(strict=True, min_length=1)
    timestamp: datetime
    measurements: dict[str, MagnitudMQTT] = Field(min_length=1)

    @field_validator("timestamp", mode="before")
    @classmethod
    def timestamp_debe_ser_texto_iso(cls, v):
        # Sin esto Pydantic aceptaría números (epoch) como fecha.
        if not isinstance(v, str):
            raise ValueError("timestamp debe ser un texto ISO 8601, ej. 2026-10-07T16:25:30Z")
        return v

    @field_validator("timestamp", mode="after")
    @classmethod
    def timestamp_con_zona_y_en_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamp debe incluir zona horaria (UTC, ej. terminar en 'Z')")
        return v.astimezone(timezone.utc)