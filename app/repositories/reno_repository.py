"""Acceso a datos de renos. Los servicios nunca usan SQLAlchemy directamente."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Reno


def listar(db: Session, estado: str | None = None) -> list[Reno]:
    stmt = select(Reno).order_by(Reno.id)
    if estado:
        stmt = stmt.where(Reno.estado == estado)
    return list(db.scalars(stmt))


def buscar_por_id(db: Session, reno_id: int, bloquear: bool = False) -> Reno | None:
    stmt = select(Reno).where(Reno.id == reno_id)
    if bloquear:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def contar_por_estado(db: Session, estado: str, bloquear: bool = False) -> int:
    stmt = select(func.count()).select_from(Reno).where(Reno.estado == estado)
    if bloquear:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def crear(db: Session, **datos) -> Reno:
    reno = Reno(**datos)
    db.add(reno)
    db.flush()
    return reno


def actualizar(db: Session, reno: Reno, **datos) -> Reno:
    for campo, valor in datos.items():
        setattr(reno, campo, valor)
    db.flush()
    return reno


def eliminar(db: Session, reno: Reno) -> None:
    db.delete(reno)
    db.flush()
