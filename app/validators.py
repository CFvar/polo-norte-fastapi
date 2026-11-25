import re
from datetime import date

from .errors import AppError
from .models import ESTADOS_RENO, TIPOS, ZONAS


def _es_entero(v) -> bool:
    # bool es subclase de int en Python: True no debe pasar como edad 1
    return isinstance(v, int) and not isinstance(v, bool)


def _es_texto(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _es_fecha(v) -> bool:
    if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return False
    try:
        date.fromisoformat(v)
        return True
    except ValueError:
        return False


def _cuerpo(body) -> dict:
    return body if isinstance(body, dict) else {}


def invalido(detalles: list[str]) -> AppError:
    return AppError(400, "VALIDACION", "La petición tiene datos inválidos", detalles)


def parse_id(valor: str) -> int:
    if not re.fullmatch(r"\d+", valor) or int(valor) == 0:
        raise AppError(400, "ID_INVALIDO", "El id debe ser un entero positivo", [f"id recibido: {valor}"])
    return int(valor)


def validar_reno(body) -> dict:
    b = _cuerpo(body)
    errores = []
    if not _es_texto(b.get("nombre")):
        errores.append("nombre es obligatorio")
    edad = b.get("edad")
    if not _es_entero(edad) or not 1 <= edad <= 25:
        errores.append("edad debe ser un entero entre 1 y 25")
    energia = b.get("nivelEnergia")
    if not _es_entero(energia) or not 0 <= energia <= 100:
        errores.append("nivelEnergia debe ser un entero entre 0 y 100")
    if "estado" in b and b["estado"] not in ESTADOS_RENO:
        errores.append(f"estado debe ser uno de: {', '.join(ESTADOS_RENO)}")
    if errores:
        raise invalido(errores)
    return b


def validar_mantenimiento(body) -> dict:
    b = _cuerpo(body)
    errores = []
    if b.get("zona") not in ZONAS:
        errores.append(f"zona debe ser una de: {', '.join(ZONAS)}")
    if b.get("tipo") not in TIPOS:
        errores.append(f"tipo debe ser uno de: {', '.join(TIPOS)}")
    fecha = b.get("fechaProgramada")
    if not _es_fecha(fecha):
        errores.append("fechaProgramada es obligatoria (formato YYYY-MM-DD)")
    elif date.fromisoformat(fecha) < date.today():
        errores.append("fechaProgramada no puede ser una fecha pasada")
    if not _es_texto(b.get("responsable")):
        errores.append("responsable es obligatorio")
    if errores:
        raise invalido(errores)
    return b


def validar_enum(valor, permitidos: list[str], campo: str) -> None:
    if valor not in permitidos:
        raise invalido([f"{campo} debe ser uno de: {', '.join(permitidos)}"])
