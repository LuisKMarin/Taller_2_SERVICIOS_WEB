import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import medicion, sensor, sensor_magnitud
from app.mqtt.client import start_mqtt, stop_mqtt

# Log en consola y en el archivo mqtt.log (el .gitignore ignora *.log).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mqtt.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("app.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranca el suscriptor MQTT junto con la API y lo detiene al cerrar."""
    cliente = start_mqtt()
    yield
    stop_mqtt(cliente)


app = FastAPI(
    title="API IoT - Taller 2",
    description="Recibe datos de un sensor IoT por MQTT, los valida y los expone.",
    lifespan=lifespan,
)

app.include_router(sensor.router)
app.include_router(sensor_magnitud.router)
app.include_router(medicion.router)


@app.exception_handler(SQLAlchemyError)
async def error_base_de_datos(request: Request, exc: SQLAlchemyError):
    logger.error("[ERROR][BASE_DE_DATOS] %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "Base de datos no disponible"})


@app.get("/", tags=["Estado"])
def raiz():
    return {"mensaje": "API IoT en funcionamiento", "documentacion": "/docs"}