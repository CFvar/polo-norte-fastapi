"""Acceso a datos de mantenimientos."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Mantenimiento


def listar(db: Session, zona: str | None = None) -> list[Mantenimiento]:
    stmt = select(Mantenimiento).order_by(Mantenimiento.id)
    if zona:
        stmt = stmt.where(Mantenimiento.zona == zona)
    return list(db.scalars(stmt))


def buscar_por_id(db: Session, mant_id: int) -> Mantenimiento | None:
    return db.get(Mantenimiento, mant_id)


def existe(db: Session, **filtros) -> bool:
    stmt = select(func.count()).select_from(Mantenimiento).filter_by(**filtros)
    return db.scalar(stmt) > 0


def crear(db: Session, **datos) -> Mantenimiento:
    mant = Mantenimiento(**datos)
    db.add(mant)
    db.flush()
    return mant


def actualizar(db: Session, mant: Mantenimiento, **datos) -> Mantenimiento:
    for campo, valor in datos.items():
        setattr(mant, campo, valor)
    db.flush()
    return mant
