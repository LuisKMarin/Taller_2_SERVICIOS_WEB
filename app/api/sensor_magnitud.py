from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.sensor import SensorId, obtener_sensor_o_404
from app.crud import sensor_magnitud as crud_sensor_magnitud
from app.database.connection import get_db
from app.schemas.sensor_magnitud import SensorMagnitudRead

router = APIRouter(tags=["Magnitudes"])

INT_MAX = 2_147_483_647
SensorMagnitudId = Annotated[int, Path(ge=1, le=INT_MAX, description="`id` de la magnitud del sensor")]


@router.get(
    "/sensores/{sensor_id}/magnitudes",
    response_model=list[SensorMagnitudRead],
    summary="Magnitudes que mide un sensor",
)
def magnitudes_de_sensor(sensor_id: SensorId, db: Session = Depends(get_db)):
    obtener_sensor_o_404(db, sensor_id)
    return crud_sensor_magnitud.get_magnitudes_por_sensor(db, sensor_id)


@router.get(
    "/sensor-magnitudes/{sensor_magnitud_id}",
    response_model=SensorMagnitudRead,
    summary="Consultar una magnitud de sensor por id",
)
def sensor_magnitud_por_id(sensor_magnitud_id: SensorMagnitudId, db: Session = Depends(get_db)):
    sm = crud_sensor_magnitud.get_sensor_magnitud(db, sensor_magnitud_id)
    if sm is None:
        raise HTTPException(
            status_code=404,
            detail=f"No existe una magnitud de sensor con id {sensor_magnitud_id}",
        )
    return sm