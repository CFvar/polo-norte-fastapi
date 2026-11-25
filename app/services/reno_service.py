"""Reglas de negocio de renos (reglas 1, 2 y 5)."""
from pymysql.constants.ER import DUP_ENTRY
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..errors import AppError
from ..models import ESTADOS_RENO, Reno
from ..repositories import mantenimiento_repository, reno_repository as repo
from ..validators import validar_enum, validar_reno

MAX_RENOS_VUELO = 9
ENERGIA_MINIMA_VUELO = 70


def _no_encontrado(reno_id: int) -> AppError:
    return AppError(404, "RENO_NO_ENCONTRADO", f"No existe el reno con id {reno_id}")


def _guardar(db: Session, operacion):
    """Ejecuta y confirma; traduce el nombre duplicado a 409."""
    try:
        resultado = operacion()
        db.commit()
        return resultado
    except IntegrityError as err:
        db.rollback()
        if err.orig.args and err.orig.args[0] == DUP_ENTRY:
            raise AppError(409, "NOMBRE_DUPLICADO", "Ya existe un reno con ese nombre", ["nombre duplicado"]) from None
        raise
    except Exception:
        db.rollback()
        raise


def listar(db: Session, estado: str | None) -> list[Reno]:
    if estado is not None:
        validar_enum(estado, ESTADOS_RENO, "estado")
    return repo.listar(db, estado)


def obtener(db: Session, reno_id: int) -> Reno:
    reno = repo.buscar_por_id(db, reno_id)
    if reno is None:
        raise _no_encontrado(reno_id)
    return reno


def crear(db: Session, body) -> Reno:
    b = validar_reno(body)
    estado = b.get("estado", "DISPONIBLE")
    # ASIGNADO_VUELO solo se alcanza con PATCH /asignacion (reglas 1 y 2)
    if estado == "ASIGNADO_VUELO":
        raise AppError(409, "ESTADO_NO_PERMITIDO",
                       "Un reno no puede registrarse ya asignado al vuelo; usa PATCH /api/renos/{id}/asignacion")
    return _guardar(db, lambda: repo.crear(
        db, nombre=b["nombre"].strip(), edad=b["edad"], nivel_energia=b["nivelEnergia"], estado=estado))


def actualizar(db: Session, reno_id: int, body) -> Reno:
    b = validar_reno(body)
    reno = obtener(db, reno_id)
    estado = b.get("estado", reno.estado)

    if estado == "ASIGNADO_VUELO":
        if reno.estado != "ASIGNADO_VUELO":
            raise AppError(409, "ESTADO_NO_PERMITIDO",
                           "Para asignar un reno al vuelo usa PATCH /api/renos/{id}/asignacion")
        # Un reno que sigue asignado debe seguir cumpliendo la regla 1
        if b["nivelEnergia"] < ENERGIA_MINIMA_VUELO:
            raise AppError(409, "ENERGIA_INSUFICIENTE",
                           f"Un reno ASIGNADO_VUELO debe mantener nivelEnergia >= {ENERGIA_MINIMA_VUELO}",
                           [f"nivelEnergia recibido: {b['nivelEnergia']}"])

    return _guardar(db, lambda: repo.actualizar(
        db, reno, nombre=b["nombre"].strip(), edad=b["edad"], nivel_energia=b["nivelEnergia"], estado=estado))


def eliminar(db: Session, reno_id: int) -> None:
    """Regla 5: no se puede eliminar un reno ASIGNADO_VUELO."""
    reno = obtener(db, reno_id)
    if reno.estado == "ASIGNADO_VUELO":
        raise AppError(409, "RENO_ASIGNADO_NO_ELIMINABLE", f"No se puede eliminar a {reno.nombre}: está ASIGNADO_VUELO")
    _guardar(db, lambda: repo.eliminar(db, reno))


def asignar(db: Session, reno_id: int) -> Reno:
    """Reglas 1 y 2 dentro de UNA transacción.

    Orden de bloqueo importante: primero el conteo con FOR UPDATE (como `estado` no tiene índice,
    MySQL bloquea toda la tabla y las asignaciones simultáneas quedan en fila) y después el reno.
    Si se bloqueara primero el reno, dos peticiones para renos distintos podrían bloquearse
    mutuamente (deadlock) y una terminaría en 500.
    """
    def operacion():
        asignados = repo.contar_por_estado(db, "ASIGNADO_VUELO", bloquear=True)
        reno = repo.buscar_por_id(db, reno_id, bloquear=True)
        if reno is None:
            raise _no_encontrado(reno_id)
        if reno.estado != "DISPONIBLE":
            raise AppError(409, "RENO_NO_DISPONIBLE",
                           f"El reno debe estar DISPONIBLE para asignarse (estado actual: {reno.estado})")
        if reno.nivel_energia < ENERGIA_MINIMA_VUELO:
            raise AppError(409, "ENERGIA_INSUFICIENTE", f"Se requiere nivelEnergia >= {ENERGIA_MINIMA_VUELO}",
                           [f"nivelEnergia actual: {reno.nivel_energia}"])
        if asignados >= MAX_RENOS_VUELO:
            raise AppError(409, "CUPO_VUELO_COMPLETO", f"Ya hay {MAX_RENOS_VUELO} renos asignados al vuelo")
        return repo.actualizar(db, reno, estado="ASIGNADO_VUELO")

    return _guardar(db, operacion)


def resumen_vuelo(db: Session) -> dict:
    """Extra: resumen del vuelo del 24 de diciembre."""
    renos = repo.listar(db, "ASIGNADO_VUELO")
    promedio = round(sum(r.nivel_energia for r in renos) / len(renos), 1) if renos else 0
    pista_lista = mantenimiento_repository.existe(db, zona="PISTA_DESPEGUE", estado="COMPLETADO")
    return {
        "renosAsignados": [{"id": r.id, "nombre": r.nombre, "nivelEnergia": r.nivel_energia} for r in renos],
        "totalAsignados": len(renos),
        "energiaPromedio": promedio,
        "pistaConMantenimientoCompletado": pista_lista,
        "vueloListo": len(renos) == MAX_RENOS_VUELO and pista_lista,
    }
