"""Manejador global de errores: TODA respuesta de error sale con el mismo formato."""
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import AppError

log = logging.getLogger("polonorte")


def _ruta(request: Request) -> str:
    q = request.url.query
    return request.url.path + (f"?{q}" if q else "")


def respuesta_error(request: Request, status: int, codigo: str, mensaje: str, detalles=None) -> JSONResponse:
    return JSONResponse(status_code=status, content={
        "codigo": codigo,
        "mensaje": mensaje,
        "detalles": detalles or [],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "ruta": _ruta(request),
    })


async def _app_error(request: Request, err: AppError):
    return respuesta_error(request, err.status, err.codigo, err.mensaje, err.detalles)


async def _validacion(request: Request, err: RequestValidationError):
    errores = err.errors()
    if any(e.get("type") == "json_invalid" for e in errores):
        return respuesta_error(request, 400, "JSON_INVALIDO", "El cuerpo de la petición no es un JSON válido")
    detalles = [f"{'.'.join(str(p) for p in e.get('loc', []))}: {e.get('msg')}" for e in errores]
    return respuesta_error(request, 400, "VALIDACION", "La petición tiene datos inválidos", detalles)


async def _http(request: Request, err: StarletteHTTPException):
    if err.status_code == 404:
        return respuesta_error(request, 404, "RUTA_NO_ENCONTRADA", f"No existe {request.method} {_ruta(request)}")
    if err.status_code == 405:
        return respuesta_error(request, 405, "METODO_NO_PERMITIDO",
                               f"{request.method} no está permitido en {request.url.path}")
    return respuesta_error(request, err.status_code, "ERROR_HTTP", str(err.detail))


async def _inesperado(request: Request, err: Exception):
    log.exception("Error no controlado", exc_info=err)
    return respuesta_error(request, 500, "ERROR_INTERNO", "Error interno del servidor")


def registrar(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validacion)
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(Exception, _inesperado)
