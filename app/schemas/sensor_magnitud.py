from pydantic import BaseModel, ConfigDict


class SensorMagnitudRead(BaseModel):
    """Una magnitud de un sensor (con unidad y rango) como la devuelven los GET."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sensor_id: int
    magnitud: str
    unidad: str
    valor_minimo: float
    valor_maximo: float