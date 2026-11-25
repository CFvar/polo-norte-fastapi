"""Controlador delgado: traduce HTTP <-> servicio y elige el código de éxito. Sin reglas de negocio."""
from typing import Any

from fastapi import Body, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import reno_service
from ..validators import parse_id

EJEMPLO = {"nombre": "Rodolfo", "edad": 5, "nivelEnergia": 90}


def listar(estado: str | None = None, db: Session = Depends(get_db)):
    return [r.to_dict() for r in reno_service.listar(db, estado)]


def obtener(id: str, db: Session = Depends(get_db)):
    return reno_service.obtener(db, parse_id(id)).to_dict()


def crear(payload: Any = Body(None, examples=[EJEMPLO]), db: Session = Depends(get_db)):
    return JSONResponse(reno_service.crear(db, payload).to_dict(), status_code=201)


def actualizar(id: str, payload: Any = Body(None, examples=[{**EJEMPLO, "estado": "EN_DESCANSO"}]),
               db: Session = Depends(get_db)):
    return reno_service.actualizar(db, parse_id(id), payload).to_dict()


def eliminar(id: str, db: Session = Depends(get_db)):
    reno_service.eliminar(db, parse_id(id))
    return Response(status_code=204)


def asignar(id: str, db: Session = Depends(get_db)):
    return reno_service.asignar(db, parse_id(id)).to_dict()


def resumen_vuelo(db: Session = Depends(get_db)):
    return reno_service.resumen_vuelo(db)
