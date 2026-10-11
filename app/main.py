import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

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


@app.get("/", tags=["estado"])
def raiz():
    return {"mensaje": "API IoT en funcionamiento", "documentacion": "/docs"}