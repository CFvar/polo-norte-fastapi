"""Rutas: mapean método + ruta -> controlador y aplican la seguridad (JWT + rol)."""
from fastapi import APIRouter, Depends

from .controllers import auth_controller as auth, mantenimiento_controller as mant, reno_controller as renos
from .security import requiere_rol

router = APIRouter()
jefe = [Depends(requiere_rol("JEFE_ESTABLO"))]

router.add_api_route("/auth/login", auth.login, methods=["POST"], tags=["auth"])

router.add_api_route("/renos", renos.crear, methods=["POST"], dependencies=jefe, tags=["renos"], status_code=201)
router.add_api_route("/renos", renos.listar, methods=["GET"], tags=["renos"])
router.add_api_route("/renos/{id}", renos.obtener, methods=["GET"], tags=["renos"])
router.add_api_route("/renos/{id}", renos.actualizar, methods=["PUT"], dependencies=jefe, tags=["renos"])
router.add_api_route("/renos/{id}", renos.eliminar, methods=["DELETE"], dependencies=jefe, tags=["renos"],
                     status_code=204)
router.add_api_route("/renos/{id}/asignacion", renos.asignar, methods=["PATCH"], dependencies=jefe, tags=["renos"])

router.add_api_route("/mantenimientos", mant.crear, methods=["POST"], tags=["mantenimientos"], status_code=201)
router.add_api_route("/mantenimientos", mant.listar, methods=["GET"], tags=["mantenimientos"])
router.add_api_route("/mantenimientos/{id}/estado", mant.cambiar_estado, methods=["PATCH"], tags=["mantenimientos"])

router.add_api_route("/vuelo/resumen", renos.resumen_vuelo, methods=["GET"], tags=["extra"])  # extra B
