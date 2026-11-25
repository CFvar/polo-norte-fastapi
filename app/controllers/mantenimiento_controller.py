"""Controlador delgado: traduce HTTP <-> servicio y elige el código de éxito. Sin reglas de negocio."""
from typing import Any

from fastapi import Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..adapters.meteo_adapter import MeteoAdapter, get_meteo_adapter
from ..database import get_db
from ..services import mantenimiento_service
from ..validators import parse_id

EJEMPLO = {"zona": "PISTA_DESPEGUE", "tipo": "LIMPIEZA_NIEVE", "fechaProgramada": "2026-12-19",
           "responsable": "Elfo Pepe"}


def listar(zona: str | None = None, db: Session = Depends(get_db)):
    return [m.to_dict() for m in mantenimiento_service.listar(db, zona)]


def crear(payload: Any = Body(None, examples=[EJEMPLO]), db: Session = Depends(get_db),
          meteo: MeteoAdapter = Depends(get_meteo_adapter)):
    r = mantenimiento_service.crear(db, payload, meteo)
    if not r.confirmado:
        # Servicio SOAP caído: 202 Accepted, se confirmará después
        return JSONResponse(status_code=202, content={
            "mensaje": "Mantenimiento recibido. El servicio meteorológico no respondió; "
                       "se confirmará cuando esté disponible.",
            "motivo": r.motivo,
            "intentos": r.intentos,
            "mantenimiento": r.mantenimiento.to_dict(),
        })
    cuerpo = r.mantenimiento.to_dict()
    if r.pronostico:
        cuerpo["pronostico"] = r.pronostico
    return JSONResponse(cuerpo, status_code=201)


def cambiar_estado(id: str, payload: Any = Body(None, examples=[{"estado": "EN_CURSO"}]),
                   db: Session = Depends(get_db)):
    return mantenimiento_service.cambiar_estado(db, parse_id(id), payload).to_dict()
