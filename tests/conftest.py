import os

# Antes de importar la app: base <DB_NAME>_test y usuarios/secretos propios de los tests
os.environ.update({
    "APP_ENV": "test",
    "JEFE_USER": "jefe", "JEFE_PASSWORD": "jefe123",
    "ELFO_USER": "elfo", "ELFO_PASSWORD": "elfo123",
    "JWT_SECRET": "secreto-de-test-solo-para-pytest-0123456789", "JWT_EXPIRES": "2h",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.adapters.meteo_adapter import get_meteo_adapter  # noqa: E402
from app.database import Base, SessionLocal, crear_base_de_datos, engine  # noqa: E402
from app.main import app  # noqa: E402


class MeteoFalso:
    """Reemplaza al adaptador SOAP en los tests de la API."""

    def __init__(self):
        self.respuesta = None
        self.error = None
        self.llamadas = []

    def obtener_pronostico(self, zona, fecha):
        self.llamadas.append((zona, fecha))
        if self.error:
            raise self.error
        return {"zona": zona, "fecha": fecha, "condicion": self.respuesta}


@pytest.fixture(scope="session", autouse=True)
def preparar_bd():
    crear_base_de_datos()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def limpiar_tablas():
    with engine.begin() as conn:
        for tabla in Base.metadata.sorted_tables:
            conn.execute(text(f"TRUNCATE TABLE `{tabla.name}`"))


@pytest.fixture
def meteo():
    falso = MeteoFalso()
    app.dependency_overrides[get_meteo_adapter] = lambda: falso
    yield falso
    app.dependency_overrides.pop(get_meteo_adapter, None)


@pytest.fixture(scope="session")
def client():
    # raise_server_exceptions=False: queremos ver el 500 con formato estándar, no la excepción
    return TestClient(app, raise_server_exceptions=False)


def _token(client, usuario, clave):
    return client.post("/api/auth/login", json={"username": usuario, "password": clave}).json()["token"]


@pytest.fixture(scope="session")
def jefe(client):
    return {"Authorization": f"Bearer {_token(client, 'jefe', 'jefe123')}"}


@pytest.fixture(scope="session")
def elfo(client):
    return {"Authorization": f"Bearer {_token(client, 'elfo', 'elfo123')}"}


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()
