from typing import Any

from fastapi import Body

from ..services import auth_service


def login(payload: Any = Body(None, examples=[{"username": "jefe", "password": "jefe123"}])):
    return auth_service.login(payload)
