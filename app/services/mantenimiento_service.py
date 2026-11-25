"""Reglas de negocio de mantenimientos (reglas 3 y 4) y manejo del fallo del SOAP."""
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from ..adapters.meteo_adapter import MeteoAdapter, ServicioExternoNoDisponibleError
from ..errors import AppError
from ..models import ESTADOS_MANT, ZONAS, Mantenimiento
from ..repositories import mantenimiento_repository as repo
from ..validators import validar_enum, validar_mantenimiento

ZONAS_EXTERIORES = ["PISTA_DESPEGUE"]

# Regla 3: transiciones permitidas (cualquier otra -> 409)
TRANSICIONES = {
    "PROGRAMADO": ["EN_CURSO", "CANCELADO"],
    "EN_CURSO": ["COMPLETADO"],
}


@dataclass
class ResultadoCreacion:
    mantenimiento: Mantenimiento
    confirmado: bool              # True -> 201 PROGRAMADO · False -> 202 PENDIENTE_CLIMA
    pronostico: str | None = None
    motivo: str | None = None
    intentos: int | None = None


def listar(db: Session, zona: str | None) -> list[Mantenimiento]:
    if zona is not None:
        validar_enum(zona, ZONAS, "zona")
    return repo.listar(db, zona)


def _guardar(db: Session, datos: dict, estado: str) -> Mantenimiento:
    try:
        mant = repo.crear(db, **datos, estado=estado)
        db.commit()
        return mant
    except Exception:
        db.rollback()
        raise


def crear(db: Session, body, meteo: MeteoAdapter) -> ResultadoCreacion:
    """Regla 4 + manejo del fallo distribuido."""
    b = validar_mantenimiento(body)
    zona, fecha = b["zona"], b["fechaProgramada"]
    datos = {"zona": zona, "tipo": b["tipo"], "fecha_programada": date.fromisoformat(fecha),
             "responsable": b["responsable"].strip()}

    if zona not in ZONAS_EXTERIORES:
        return ResultadoCreacion(_guardar(db, datos, "PROGRAMADO"), confirmado=True)

    try:
        pronostico = meteo.obtener_pronostico(zona, fecha)
    except ServicioExternoNoDisponibleError as err:
        # Fault o timeout: se guarda igual, pendiente de confirmar el clima. Nunca 500.
        return ResultadoCreacion(_guardar(db, datos, "PENDIENTE_CLIMA"), confirmado=False,
                                 motivo=err.motivo, intentos=err.intentos)

    if pronostico["condicion"] == "VENTISCA":
        raise AppError(422, "PRONOSTICO_VENTISCA",
                       f"No se puede programar un mantenimiento en {zona} el {fecha}: el pronóstico es VENTISCA")
    return ResultadoCreacion(_guardar(db, datos, "PROGRAMADO"), confirmado=True, pronostico=pronostico["condicion"])


def cambiar_estado(db: Session, mant_id: int, body) -> Mantenimiento:
    nuevo = body.get("estado") if isinstance(body, dict) else None
    validar_enum(nuevo, ESTADOS_MANT, "estado")
    mant = repo.buscar_por_id(db, mant_id)
    if mant is None:
        raise AppError(404, "MANTENIMIENTO_NO_ENCONTRADO", f"No existe el mantenimiento con id {mant_id}")

    permitidos = TRANSICIONES.get(mant.estado, [])
    if nuevo not in permitidos:
        detalle = (f"desde {mant.estado} solo se permite: {', '.join(permitidos)}" if permitidos
                   else f"{mant.estado} no admite transiciones")
        raise AppError(409, "TRANSICION_INVALIDA", f"No se puede pasar de {mant.estado} a {nuevo}", [detalle])

    try:
        repo.actualizar(db, mant, estado=nuevo)
        db.commit()
        return mant
    except Exception:
        db.rollback()
        raise
