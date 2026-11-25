"""Middleware de seguridad (dependencias de FastAPI): JWT -> 401, rol -> 403."""
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import jwt_secret
from .errors import AppError

# auto_error=False: así el 401 sale con nuestro formato de error y no con el de FastAPI
bearer = HTTPBearer(auto_error=False, description="Token obtenido en POST /api/auth/login")


def usuario_actual(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if cred is None or not cred.credentials:
        raise AppError(401, "TOKEN_REQUERIDO", "Se requiere un token: Authorization: Bearer <token>")
    try:
        return jwt.decode(cred.credentials, jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise AppError(401, "TOKEN_INVALIDO", "El token es inválido o expiró") from None


def requiere_rol(*roles: str):
    def verificar(usuario: dict = Depends(usuario_actual)) -> dict:
        if usuario.get("rol") not in roles:
            raise AppError(403, "ROL_INSUFICIENTE", f"Esta operación requiere el rol {' o '.join(roles)}",
                           [f"rol actual: {usuario.get('rol')}"])
        return usuario

    return verificar
