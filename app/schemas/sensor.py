from pydantic import BaseModel, ConfigDict, Field

from app.schemas.medicion import FechaColombia


class SensorRead(BaseModel):
    """Un sensor del catálogo tal como lo devuelven los endpoints GET."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str
    categoria: str
    ubicacion: str
    activo: bool
    fecha_registro_colombia: FechaColombia = Field(validation_alias="fecha_registro")