"""Punto de entrada de la API (uvicorn app.main:app)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import error_handlers, models  # noqa: F401 - registra los modelos en Base.metadata
from .config import validar_config
from .database import Base, crear_base_de_datos, engine
from .routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validar_config()
    crear_base_de_datos()             # crea DB_NAME si no existe
    Base.metadata.create_all(engine)  # crea las tablas si no existen
    yield
    engine.dispose()


app = FastAPI(
    title="API Polo Norte · Escenario B",
    description="Establo de renos y mantenimiento del terreno. Integra el SOAP MeteoPoloNorteService.",
    version="1.0.0",
    lifespan=lifespan,
)
error_handlers.registrar(app)


@app.get("/health", tags=["extra"])
def health():
    return {"status": "ok"}


app.include_router(router, prefix="/api")
