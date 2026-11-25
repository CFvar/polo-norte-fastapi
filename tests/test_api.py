import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from app.adapters.meteo_adapter import ServicioExternoNoDisponibleError
from app.models import Mantenimiento, Reno

FUTURA = "2030-12-20"


def formato_error(res, status, codigo):
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"codigo", "mensaje", "detalles", "timestamp", "ruta"}
    assert body["codigo"] == codigo
    assert isinstance(body["mensaje"], str) and isinstance(body["detalles"], list)
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", body["timestamp"])
    return body


def crear_renos_asignados(db, n, energia=90):
    """Inserta n renos ya asignados (energía energia, energia+1, ...)."""
    db.add_all([Reno(nombre=f"R{i}", edad=5, nivel_energia=energia + i, estado="ASIGNADO_VUELO") for i in range(n)])
    db.commit()


@pytest.fixture
def nuevo_reno(client, jefe):
    def _crear(**data):
        return client.post("/api/renos", headers=jefe, json={"nombre": "Rodolfo", "edad": 5, "nivelEnergia": 90, **data})
    return _crear


# --- Seguridad ---------------------------------------------------------------
class TestSeguridad:
    def test_sin_token_401(self, client):
        res = client.post("/api/renos", json={"nombre": "X", "edad": 1, "nivelEnergia": 1})
        assert formato_error(res, 401, "TOKEN_REQUERIDO")["ruta"] == "/api/renos"

    def test_rol_elfo_403(self, client, elfo):
        res = client.post("/api/renos", headers=elfo, json={"nombre": "X", "edad": 1, "nivelEnergia": 1})
        formato_error(res, 403, "ROL_INSUFICIENTE")

    def test_token_invalido_401(self, client):
        formato_error(client.delete("/api/renos/1", headers={"Authorization": "Bearer x.y.z"}), 401, "TOKEN_INVALIDO")

    def test_login_invalido_401(self, client):
        res = client.post("/api/auth/login", json={"username": "jefe", "password": "mal"})
        formato_error(res, 401, "CREDENCIALES_INVALIDAS")

    def test_login_sin_datos_400(self, client):
        formato_error(client.post("/api/auth/login", json={}), 400, "VALIDACION")

    def test_get_renos_es_publico(self, client):
        assert client.get("/api/renos").status_code == 200


# --- Renos -------------------------------------------------------------------
class TestRenos:
    def test_crea_201_disponible(self, nuevo_reno):
        res = nuevo_reno()
        assert res.status_code == 201
        assert res.json()["nombre"] == "Rodolfo" and res.json()["estado"] == "DISPONIBLE"

    def test_nombre_duplicado_409(self, nuevo_reno):
        nuevo_reno()
        formato_error(nuevo_reno(), 409, "NOMBRE_DUPLICADO")

    @pytest.mark.parametrize("data", [
        {"edad": 0}, {"edad": 26}, {"nivelEnergia": -1}, {"nivelEnergia": 101}, {"nombre": ""},
        {"estado": "VOLANDO"}, {"edad": "5"}, {"edad": True}, {"nivelEnergia": 50.5},
    ])
    def test_validacion_400(self, nuevo_reno, data):
        formato_error(nuevo_reno(**data), 400, "VALIDACION")

    def test_registrar_ya_asignado_409(self, nuevo_reno):
        formato_error(nuevo_reno(estado="ASIGNADO_VUELO"), 409, "ESTADO_NO_PERMITIDO")

    def test_detalle_200(self, client, nuevo_reno):
        reno_id = nuevo_reno().json()["id"]
        res = client.get(f"/api/renos/{reno_id}")
        assert res.status_code == 200 and res.json()["id"] == reno_id

    def test_filtra_por_estado(self, client, nuevo_reno):
        nuevo_reno(nombre="A")
        nuevo_reno(nombre="B", estado="EN_DESCANSO")
        assert [r["nombre"] for r in client.get("/api/renos?estado=EN_DESCANSO").json()] == ["B"]

    def test_filtro_estado_invalido_400(self, client):
        formato_error(client.get("/api/renos?estado=VOLANDO"), 400, "VALIDACION")

    def test_detalle_inexistente_404(self, client):
        formato_error(client.get("/api/renos/9999"), 404, "RENO_NO_ENCONTRADO")

    def test_put_actualiza(self, client, jefe, nuevo_reno):
        reno_id = nuevo_reno().json()["id"]
        res = client.put(f"/api/renos/{reno_id}", headers=jefe,
                         json={"nombre": "Rodolfo", "edad": 6, "nivelEnergia": 50, "estado": "EN_REVISION"})
        assert res.status_code == 200
        assert res.json()["edad"] == 6 and res.json()["estado"] == "EN_REVISION"


# --- Reglas 1 y 2 -------------------------------------------------------------
class TestAsignacion:
    @pytest.fixture
    def asignar(self, client, jefe):
        return lambda reno_id: client.patch(f"/api/renos/{reno_id}/asignacion", headers=jefe)

    def test_disponible_con_energia_70_200(self, nuevo_reno, asignar):
        res = asignar(nuevo_reno(nivelEnergia=70).json()["id"])
        assert res.status_code == 200 and res.json()["estado"] == "ASIGNADO_VUELO"

    def test_energia_menor_70_409(self, nuevo_reno, asignar):
        formato_error(asignar(nuevo_reno(nivelEnergia=69).json()["id"]), 409, "ENERGIA_INSUFICIENTE")

    def test_no_disponible_409(self, nuevo_reno, asignar):
        formato_error(asignar(nuevo_reno(estado="EN_DESCANSO").json()["id"]), 409, "RENO_NO_DISPONIBLE")

    def test_inexistente_404(self, asignar):
        formato_error(asignar(9999), 404, "RENO_NO_ENCONTRADO")

    def test_decimo_reno_409(self, db, nuevo_reno, asignar):
        crear_renos_asignados(db, 9)
        formato_error(asignar(nuevo_reno(nombre="Decimo").json()["id"]), 409, "CUPO_VUELO_COMPLETO")

    def test_put_no_salta_la_regla_409(self, client, jefe, nuevo_reno):
        reno_id = nuevo_reno(nivelEnergia=10).json()["id"]
        res = client.put(f"/api/renos/{reno_id}", headers=jefe,
                         json={"nombre": "Rodolfo", "edad": 5, "nivelEnergia": 10, "estado": "ASIGNADO_VUELO"})
        formato_error(res, 409, "ESTADO_NO_PERMITIDO")

    def test_put_no_baja_energia_de_un_asignado_409(self, client, jefe, nuevo_reno, asignar):
        reno_id = nuevo_reno().json()["id"]
        asignar(reno_id)
        res = client.put(f"/api/renos/{reno_id}", headers=jefe,
                         json={"nombre": "Rodolfo", "edad": 5, "nivelEnergia": 20})
        formato_error(res, 409, "ENERGIA_INSUFICIENTE")

    def test_asignaciones_simultaneas_no_superan_el_cupo(self, client, db, nuevo_reno, asignar):
        """Regla 2 con concurrencia: 8 asignados + 4 peticiones a la vez -> solo 1 entra, sin 500."""
        crear_renos_asignados(db, 8)
        ids = [nuevo_reno(nombre=f"Candidato{i}").json()["id"] for i in range(4)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            codigos = sorted(r.status_code for r in pool.map(asignar, ids))
        assert codigos == [200, 409, 409, 409]
        assert len(client.get("/api/renos?estado=ASIGNADO_VUELO").json()) == 9


# --- Regla 5 ------------------------------------------------------------------
class TestEliminar:
    def test_disponible_204(self, client, jefe, nuevo_reno):
        reno_id = nuevo_reno().json()["id"]
        res = client.delete(f"/api/renos/{reno_id}", headers=jefe)
        assert res.status_code == 204 and res.content == b""
        assert client.get(f"/api/renos/{reno_id}").status_code == 404

    def test_asignado_409(self, client, jefe, db):
        reno = Reno(nombre="Volador", edad=5, nivel_energia=90, estado="ASIGNADO_VUELO")
        db.add(reno)
        db.commit()
        formato_error(client.delete(f"/api/renos/{reno.id}", headers=jefe), 409, "RENO_ASIGNADO_NO_ELIMINABLE")


# --- Reglas 3 y 4 + fallo del SOAP ---------------------------------------------------
class TestMantenimientos:
    @pytest.fixture
    def crear_mant(self, client):
        def _crear(**data):
            return client.post("/api/mantenimientos", json={
                "zona": "ESTABLO", "tipo": "INSPECCION", "fechaProgramada": FUTURA, "responsable": "Elfo Pepe", **data})
        return _crear

    @pytest.fixture
    def cambiar(self, client):
        return lambda mant_id, estado: client.patch(f"/api/mantenimientos/{mant_id}/estado", json={"estado": estado})

    def test_zona_interior_no_consulta_clima_201(self, crear_mant, meteo):
        res = crear_mant()
        assert res.status_code == 201 and res.json()["estado"] == "PROGRAMADO"
        assert meteo.llamadas == []

    def test_fecha_pasada_400(self, crear_mant, meteo):
        formato_error(crear_mant(fechaProgramada="2020-01-01"), 400, "VALIDACION")

    def test_fecha_inexistente_400(self, crear_mant, meteo):
        formato_error(crear_mant(fechaProgramada="2030-02-30"), 400, "VALIDACION")

    def test_pista_despejado_201(self, crear_mant, meteo):
        meteo.respuesta = "DESPEJADO"
        res = crear_mant(zona="PISTA_DESPEGUE")
        assert res.status_code == 201
        assert res.json()["estado"] == "PROGRAMADO" and res.json()["pronostico"] == "DESPEJADO"
        assert meteo.llamadas == [("PISTA_DESPEGUE", FUTURA)]

    def test_pista_ventisca_422(self, crear_mant, meteo, db):
        meteo.respuesta = "VENTISCA"
        formato_error(crear_mant(zona="PISTA_DESPEGUE"), 422, "PRONOSTICO_VENTISCA")
        assert db.query(Mantenimiento).count() == 0

    def test_soap_caido_202_pendiente_clima(self, crear_mant, meteo, db):
        meteo.error = ServicioExternoNoDisponibleError("soap:Server: Estación sin señal", 2)
        res = crear_mant(zona="PISTA_DESPEGUE")
        assert res.status_code == 202
        body = res.json()
        assert body["mantenimiento"]["estado"] == "PENDIENTE_CLIMA"
        assert "Estación sin señal" in body["motivo"] and body["intentos"] == 2
        assert db.get(Mantenimiento, body["mantenimiento"]["id"]).estado == "PENDIENTE_CLIMA"

    def test_error_inesperado_no_se_disfraza_de_202(self, crear_mant, meteo):
        meteo.error = TypeError("bug")
        formato_error(crear_mant(zona="PISTA_DESPEGUE"), 500, "ERROR_INTERNO")

    def test_filtra_por_zona(self, client, crear_mant, meteo):
        crear_mant()
        crear_mant(zona="BODEGA_REGALOS")
        assert len(client.get("/api/mantenimientos?zona=BODEGA_REGALOS").json()) == 1

    def test_programado_en_curso_completado(self, crear_mant, cambiar, meteo):
        mant_id = crear_mant().json()["id"]
        assert cambiar(mant_id, "EN_CURSO").status_code == 200
        assert cambiar(mant_id, "COMPLETADO").json()["estado"] == "COMPLETADO"

    def test_programado_cancelado(self, crear_mant, cambiar, meteo):
        assert cambiar(crear_mant().json()["id"], "CANCELADO").status_code == 200

    @pytest.mark.parametrize("desde,hacia", [
        ("PROGRAMADO", "COMPLETADO"), ("EN_CURSO", "CANCELADO"), ("COMPLETADO", "EN_CURSO"),
        ("CANCELADO", "PROGRAMADO"), ("PENDIENTE_CLIMA", "EN_CURSO"),
    ])
    def test_transicion_invalida_409(self, crear_mant, cambiar, meteo, db, desde, hacia):
        mant_id = crear_mant().json()["id"]
        db.get(Mantenimiento, mant_id).estado = desde
        db.commit()
        formato_error(cambiar(mant_id, hacia), 409, "TRANSICION_INVALIDA")

    def test_estado_invalido_400(self, crear_mant, cambiar, meteo):
        formato_error(cambiar(crear_mant().json()["id"], "VOLANDO"), 400, "VALIDACION")

    def test_mantenimiento_inexistente_404(self, cambiar):
        formato_error(cambiar(9999, "EN_CURSO"), 404, "MANTENIMIENTO_NO_ENCONTRADO")


# --- Formato de errores y extras ---------------------------------------------------
class TestFormatoYExtras:
    def test_ruta_inexistente_404(self, client):
        formato_error(client.get("/api/nada"), 404, "RUTA_NO_ENCONTRADA")

    def test_metodo_no_permitido_405(self, client):
        formato_error(client.patch("/api/renos"), 405, "METODO_NO_PERMITIDO")

    def test_json_mal_formado_400(self, client):
        res = client.post("/api/mantenimientos", content="{malo", headers={"Content-Type": "application/json"})
        formato_error(res, 400, "JSON_INVALIDO")

    def test_id_no_numerico_400(self, client):
        formato_error(client.get("/api/renos/abc"), 400, "ID_INVALIDO")

    def test_resumen_vuelo(self, client, db):
        crear_renos_asignados(db, 9, energia=80)
        res = client.get("/api/vuelo/resumen").json()
        assert res["totalAsignados"] == 9 and res["energiaPromedio"] == 84 and res["vueloListo"] is False
        db.add(Mantenimiento(zona="PISTA_DESPEGUE", tipo="LIMPIEZA_NIEVE", fecha_programada=date(2030, 12, 20),
                             responsable="x", estado="COMPLETADO"))
        db.commit()
        assert client.get("/api/vuelo/resumen").json()["vueloListo"] is True
