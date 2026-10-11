from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.crud import sensor as crud_sensor
from app.database.connection import get_db
from app.schemas.sensor import SensorRead

router = APIRouter(tags=["Sensores"])

INT_MAX = 2_147_483_647  # límite del INTEGER de PostgreSQL
SensorId = Annotated[int, Path(ge=1, le=INT_MAX, description="`id` numérico del sensor")]


def obtener_sensor_o_404(db: Session, sensor_id: int):
    """Devuelve el sensor o lanza 404. Lo reutilizan los otros routers."""
    sensor = crud_sensor.get_sensor(db, sensor_id)
    if sensor is None:
        raise HTTPException(status_code=404, detail=f"No existe un sensor con id {sensor_id}")
    return sensor


@router.get("/sensores", response_model=list[SensorRead], summary="Listar sensores")
def listar_sensores(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    db: Session = Depends(get_db),
):
    return crud_sensor.get_sensores(db, skip=skip, limit=limit)


@router.get(
    "/sensores/por-codigo/{codigo}",
    response_model=SensorRead,
    summary="Consultar un sensor por su código (ej. GAS-005)",
)
def sensor_por_codigo(codigo: str, db: Session = Depends(get_db)):
    sensor = crud_sensor.get_sensor_por_codigo(db, codigo)
    if sensor is None:
        raise HTTPException(status_code=404, detail=f"No existe un sensor con código '{codigo}'")
    return sensor


@router.get("/sensores/{sensor_id}", response_model=SensorRead, summary="Consultar un sensor por id")
def sensor_por_id(sensor_id: SensorId, db: Session = Depends(get_db)):
    return obtener_sensor_o_404(db, sensor_id)