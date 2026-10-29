from contextlib import asynccontextmanager
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .config import settings
from .db import Base, SessionLocal, engine
from .routers import auth, commands, devices, ingest, reports
from .services.local_llm import get_model_name, is_available as local_llm_available


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.get(models.Device, "hi3861_001") is None:
            db.add(models.Device(device_id="hi3861_001", name="工位1"))
            db.add(models.DeviceConfig(device_id="hi3861_001"))
            db.commit()
    mqtt_stop = threading.Event()
    mqtt_thread = None
    if (
        settings.iotda_app_mqtt_enabled
        and settings.iotda_app_mqtt_configured
    ):
        from .services.cloud_sync import run_mqtt_subscriber

        mqtt_thread = threading.Thread(
            target=run_mqtt_subscriber,
            args=(mqtt_stop,),
            name="iotda-mqtt-subscriber",
            daemon=True,
        )
        mqtt_thread.start()
    try:
        yield
    finally:
        if mqtt_thread is not None:
            mqtt_stop.set()
            mqtt_thread.join(timeout=3)


app = FastAPI(
    title="Eye Care Desk API",
    description="工位用眼健康与桌面微环境监护系统后端",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(commands.router)
app.include_router(commands.actions)
app.include_router(reports.router)
app.include_router(ingest.router)


@app.get("/health", tags=["system"])
def health():
    return {
        "status": "ok",
        "service": "eye-care-api",
        "version": "0.1.0",
        "ai": {
            "local_available": local_llm_available(),
            "local_model": get_model_name() if local_llm_available() else None,
            "remote_configured": bool(settings.llm_api_url),
        },
    }
