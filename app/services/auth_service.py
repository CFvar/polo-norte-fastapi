import hmac
from datetime import datetime, timedelta, timezone

import jwt

from ..config import env, jwt_expira_segundos, jwt_secret
from ..errors import AppError


def _usuarios() -> list[dict]:
    """Usuarios de prueba definidos por variables de entorno (sin secretos en el repo)."""
    usuarios = [
        {"username": env("JEFE_USER"), "password": env("JEFE_PASSWORD"), "rol": "JEFE_ESTABLO"},
        {"username": env("ELFO_USER"), "password": env("ELFO_PASSWORD"), "rol": "ELFO"},
    ]
    return [u for u in usuarios if u["username"] and u["password"]]


def login(body) -> dict:
    b = body if isinstance(body, dict) else {}
    username, password = b.get("username"), b.get("password")
    if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
        raise AppError(400, "VALIDACION", "username y password son obligatorios")

    def igual(a: str, b: str) -> bool:  # comparación en tiempo constante
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

    usuario = next(
        (u for u in _usuarios() if igual(u["username"], username) and igual(u["password"], password)),
        None,
    )
    if usuario is None:
        raise AppError(401, "CREDENCIALES_INVALIDAS", "Usuario o contraseña incorrectos")

    ahora = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": usuario["username"], "rol": usuario["rol"], "iat": ahora,
         "exp": ahora + timedelta(seconds=jwt_expira_segundos())},
        jwt_secret(),
        algorithm="HS256",
    )
    return {"token": token, "rol": usuario["rol"]}
