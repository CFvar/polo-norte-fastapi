"""Configuración leída de variables de entorno (.env). Nunca hay secretos en el código."""
import os
import re

from dotenv import load_dotenv

load_dotenv()  # no sobrescribe variables ya definidas (los tests definen las suyas)


def env(nombre: str, defecto: str | None = None) -> str | None:
    valor = os.getenv(nombre)
    return valor if valor not in (None, "") else defecto


def env_int(nombre: str, defecto: int) -> int:
    return int(env(nombre, str(defecto)))


def jwt_secret() -> str:
    secreto = env("JWT_SECRET")
    if not secreto:
        raise RuntimeError("Falta la variable de entorno JWT_SECRET")
    return secreto


def jwt_expira_segundos() -> int:
    """Convierte '2h', '30m', '45s', '1d' o '3600' a segundos."""
    texto = env("JWT_EXPIRES", "2h")
    m = re.fullmatch(r"(\d+)\s*([smhd]?)", texto.strip())
    if not m:
        raise RuntimeError(f"JWT_EXPIRES inválido: {texto}")
    return int(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def validar_config() -> None:
    """Se llama al arrancar: falla rápido si falta algo obligatorio."""
    jwt_secret()
    jwt_expira_segundos()
