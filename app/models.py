from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

ESTADOS_RENO = ["DISPONIBLE", "EN_DESCANSO", "EN_REVISION", "ASIGNADO_VUELO"]
ZONAS = ["PISTA_DESPEGUE", "ESTABLO", "BODEGA_REGALOS", "HANGAR_TRINEO"]
TIPOS = ["LIMPIEZA_NIEVE", "REPARACION", "INSPECCION"]
ESTADOS_MANT = ["PROGRAMADO", "EN_CURSO", "COMPLETADO", "CANCELADO", "PENDIENTE_CLIMA"]


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="milliseconds") + "Z" if dt else None


class Reno(Base):
    __tablename__ = "renos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    edad: Mapped[int] = mapped_column(Integer, nullable=False)
    nivel_energia: Mapped[int] = mapped_column("nivelEnergia", Integer, nullable=False)
    estado: Mapped[str] = mapped_column(Enum(*ESTADOS_RENO, name="estado_reno"), nullable=False, default="DISPONIBLE")
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=_ahora)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, default=_ahora, onupdate=_ahora)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "edad": self.edad,
            "nivelEnergia": self.nivel_energia,
            "estado": self.estado,
            "createdAt": _iso(self.created_at),
            "updatedAt": _iso(self.updated_at),
        }


class Mantenimiento(Base):
    __tablename__ = "mantenimientos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zona: Mapped[str] = mapped_column(Enum(*ZONAS, name="zona"), nullable=False)
    tipo: Mapped[str] = mapped_column(Enum(*TIPOS, name="tipo"), nullable=False)
    fecha_programada: Mapped[date] = mapped_column("fechaProgramada", Date, nullable=False)
    responsable: Mapped[str] = mapped_column(String(100), nullable=False)
    estado: Mapped[str] = mapped_column(Enum(*ESTADOS_MANT, name="estado_mant"), nullable=False, default="PROGRAMADO")
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=_ahora)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, default=_ahora, onupdate=_ahora)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "zona": self.zona,
            "tipo": self.tipo,
            "fechaProgramada": self.fecha_programada.isoformat(),
            "responsable": self.responsable,
            "estado": self.estado,
            "createdAt": _iso(self.created_at),
            "updatedAt": _iso(self.updated_at),
        }
