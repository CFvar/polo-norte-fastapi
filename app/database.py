"""Conexión a MySQL con SQLAlchemy 2."""
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import env, env_int


def nombre_bd() -> str:
    nombre = env("DB_NAME", "polonorte_py")
    if env("APP_ENV") == "test":
        nombre = f"{nombre}_test"
    if not re.fullmatch(r"\w+", nombre):
        raise RuntimeError(f"DB_NAME inválido: {nombre}")
    return nombre


def _url(database: str | None = None) -> URL:
    return URL.create(
        "mysql+pymysql",
        username=env("DB_USER", "root"),
        password=env("DB_PASS"),
        host=env("DB_HOST", "127.0.0.1"),
        port=env_int("DB_PORT", 3306),
        database=database,
        query={"charset": "utf8mb4"},
    )


engine = create_engine(_url(nombre_bd()), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def crear_base_de_datos() -> None:
    """Crea la base de datos si no existe (comodidad para el examen)."""
    servidor = create_engine(_url())
    with servidor.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{nombre_bd()}` CHARACTER SET utf8mb4"))
    servidor.dispose()


def get_db():
    """Dependencia de FastAPI: una sesión por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
