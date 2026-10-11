from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.sensor import SensorId, obtener_sensor_o_404
from app.crud import medicion as crud_medicion
from app.crud import sensor_magnitud as crud_sensor_magnitud
from app.database.connection import get_db
from app.schemas.medicion import COLOMBIA, MedicionRead

router = APIRouter(tags=["Mediciones"])

BIGINT_MAX = 9_223_372_036_854_775_807  # límite del BIGINT de PostgreSQL
MedicionId = Annotated[int, Path(ge=1, le=BIGINT_MAX, description="`id` de la medición")]


def _a_utc(valor: datetime | None) -> datetime | None:
    """Convierte un filtro de fecha a UTC.

    Si llega sin zona horaria (ej. 2026-10-10T21:40:00) se interpreta como
    hora de Colombia, que es la que muestran las respuestas.
    Si trae zona (ej. ...Z o ...-05:00) se respeta.
    """
    if valor is None:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=COLOMBIA)
    return valor.astimezone(timezone.utc)


@router.get(
    "/sensores/{sensor_id}/mediciones",
    response_model=list[MedicionRead],
    summary="Histórico de mediciones de un sensor (filtros combinables)",
)
def mediciones_de_sensor(
    sensor_id: SensorId,
    magnitud: Annotated[str | None, Query(description="Ej. temperature, nh3, humidity")] = None,
    desde: Annotated[datetime | None, Query(description="Inicio del rango. Sin zona = hora de Colombia")] = None,
    hasta: Annotated[datetime | None, Query(description="Fin del rango. Sin zona = hora de Colombia")] = None,
    limit: Annotated[int | None, Query(ge=1, le=10000, description="Últimas N mediciones")] = None,
    db: Session = Depends(get_db),
):
    obtener_sensor_o_404(db, sensor_id)

    if magnitud is not None:
        if crud_sensor_magnitud.get_magnitud_de_sensor(db, sensor_id, magnitud) is None:
            raise HTTPException(
                status_code=404,
                detail=f"El sensor {sensor_id} no tiene la magnitud '{magnitud}'",
            )

    desde_utc, hasta_utc = _a_utc(desde), _a_utc(hasta)
    if desde_utc is not None and hasta_utc is not None and desde_utc > hasta_utc:
        raise HTTPException(
            status_code=400,
            detail="Rango de fechas inválido: 'desde' no puede ser mayor que 'hasta'",
        )

    return crud_medicion.get_mediciones_por_sensor(
        db, sensor_id, magnitud=magnitud, desde=desde_utc, hasta=hasta_utc, limit=limit
    )


@router.get(
    "/sensores/{sensor_id}/ultima-medicion",
    response_model=list[MedicionRead],
    summary="Última lectura del sensor (una medición por magnitud)",
)
def ultima_medicion(sensor_id: SensorId, db: Session = Depends(get_db)):
    obtener_sensor_o_404(db, sensor_id)
    lectura = crud_medicion.get_ultima_lectura(db, sensor_id)
    if not lectura:
        raise HTTPException(status_code=404, detail=f"El sensor {sensor_id} aún no tiene mediciones")
    return lectura


@router.get("/mediciones/{medicion_id}", response_model=MedicionRead, summary="Consultar una medición por id")
def medicion_por_id(medicion_id: MedicionId, db: Session = Depends(get_db)):
    medicion = crud_medicion.get_medicion(db, medicion_id)
    if medicion is None:
        raise HTTPException(status_code=404, detail=f"No existe una medición con id {medicion_id}")
    return medicion