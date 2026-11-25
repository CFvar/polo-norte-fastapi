"""Genera postman/PoloNorte-EscenarioB-FastAPI.postman_collection.json.

Uso:  python scripts/generar_postman.py
"""
import json
from pathlib import Path

SALIDA = Path(__file__).resolve().parent.parent / "postman" / "PoloNorte-EscenarioB-FastAPI.postman_collection.json"

JEFE = "Bearer {{tokenJefe}}"
ELFO = "Bearer {{tokenElfo}}"


def js(*lineas: str) -> list[str]:
    return list(lineas)


def espera(status: int, codigo: str | None = None) -> list[str]:
    lineas = [f"pm.test('HTTP {status}', () => pm.response.to.have.status({status}));"]
    if codigo:
        lineas.append(f"pm.test('codigo = {codigo}', () => pm.expect(pm.response.json().codigo).to.eql('{codigo}'));")
    return lineas


def req(nombre, metodo, ruta, tests, body=None, token=None, pre=None, desc=None):
    headers = []
    if body is not None:
        headers.append({"key": "Content-Type", "value": "application/json"})
    if token:
        headers.append({"key": "Authorization", "value": token})
    ruta_sin_query, _, query = ruta.partition("?")
    url = {"raw": "{{baseUrl}}" + ruta, "host": ["{{baseUrl}}"], "path": [p for p in ruta_sin_query.split("/") if p]}
    if query:
        url["query"] = [{"key": k, "value": v} for k, v in (q.split("=", 1) for q in query.split("&"))]
    item = {
        "name": nombre,
        "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": tests}}],
        "request": {"method": metodo, "header": headers, "url": url},
    }
    if pre:
        item["event"].insert(0, {"listen": "prerequest", "script": {"type": "text/javascript", "exec": pre}})
    if body is not None:
        item["request"]["body"] = {"mode": "raw", "raw": json.dumps(body, ensure_ascii=False, indent=2),
                                   "options": {"raw": {"language": "json"}}}
    if desc:
        item["request"]["description"] = desc
    return item


def login(nombre, usuario, clave, guardar=None, status=200, codigo=None):
    tests = espera(status, codigo)
    if guardar:
        tests += [
            "const b = pm.response.json();",
            "pm.test('devuelve token y rol', () => { pm.expect(b.token).to.be.a('string'); pm.expect(b.rol).to.be.a('string'); });",
            f"pm.collectionVariables.set('{guardar}', b.token);",
        ]
    return req(nombre, "POST", "/auth/login", tests, body={"username": usuario, "password": clave})


RENO = {"nombre": "{{renoNombre}}", "edad": 5, "nivelEnergia": 90}
MANT = {"zona": "ESTABLO", "tipo": "INSPECCION", "fechaProgramada": "{{fechaManana}}", "responsable": "Elfo Pepe"}

auth = [
    login("Login JEFE_ESTABLO - 200", "{{jefeUser}}", "{{jefePassword}}", guardar="tokenJefe"),
    login("Login ELFO - 200", "{{elfoUser}}", "{{elfoPassword}}", guardar="tokenElfo"),
    login("Login credenciales incorrectas - 401", "{{jefeUser}}", "clave-mala", status=401, codigo="CREDENCIALES_INVALIDAS"),
]

renos = [
    req("Registrar reno - 201", "POST", "/renos", body=RENO, token=JEFE,
        pre=js("pm.collectionVariables.set('renoNombre', 'Rodolfo-' + Date.now());"),
        tests=espera(201) + [
            "const b = pm.response.json();",
            "pm.test('estado DISPONIBLE', () => pm.expect(b.estado).to.eql('DISPONIBLE'));",
            "pm.collectionVariables.set('renoId', b.id);",
        ]),
    req("Ver detalle - 200", "GET", "/renos/{{renoId}}", tests=espera(200) + [
        "pm.test('es el reno creado', () => pm.expect(String(pm.response.json().id)).to.eql(pm.collectionVariables.get('renoId')));",
    ]),
    req("Listar con filtro estado - 200", "GET", "/renos?estado=DISPONIBLE", tests=espera(200) + [
        "pm.test('todos DISPONIBLE', () => pm.response.json().forEach(r => pm.expect(r.estado).to.eql('DISPONIBLE')));",
    ]),
    req("Registrar reno inválido - 400", "POST", "/renos", token=JEFE,
        body={"nombre": "", "edad": 0, "nivelEnergia": 150},
        tests=espera(400, "VALIDACION") + [
            "pm.test('lista los 3 errores', () => pm.expect(pm.response.json().detalles).to.have.lengthOf(3));",
        ]),
    req("Id no numérico - 400", "GET", "/renos/abc", tests=espera(400, "ID_INVALIDO")),
    req("Nombre duplicado - 409", "POST", "/renos", body=RENO, token=JEFE, tests=espera(409, "NOMBRE_DUPLICADO")),
    req("Reno inexistente - 404", "GET", "/renos/999999", tests=espera(404, "RENO_NO_ENCONTRADO")),
    req("Registrar sin token - 401", "POST", "/renos", body=RENO, tests=espera(401, "TOKEN_REQUERIDO")),
    req("Registrar con token inválido - 401", "POST", "/renos", body=RENO, token="Bearer token.falso.123",
        tests=espera(401, "TOKEN_INVALIDO")),
    req("Registrar con rol ELFO - 403", "POST", "/renos", body=RENO, token=ELFO, tests=espera(403, "ROL_INSUFICIENTE")),
    req("Actualizar datos - 200", "PUT", "/renos/{{renoId}}", token=JEFE,
        body={"nombre": "{{renoNombre}}", "edad": 6, "nivelEnergia": 95},
        tests=espera(200) + ["pm.test('edad actualizada', () => pm.expect(pm.response.json().edad).to.eql(6));"]),
    req("Asignar al vuelo - 200", "PATCH", "/renos/{{renoId}}/asignacion", token=JEFE,
        desc="Si ya hay 9 renos asignados de corridas anteriores responde 409 CUPO_VUELO_COMPLETO (regla 2).",
        tests=espera(200) + ["pm.test('ASIGNADO_VUELO', () => pm.expect(pm.response.json().estado).to.eql('ASIGNADO_VUELO'));"]),
    req("Asignar otra vez - 409 (regla 1)", "PATCH", "/renos/{{renoId}}/asignacion", token=JEFE,
        tests=espera(409, "RENO_NO_DISPONIBLE")),
    req("Eliminar reno asignado - 409 (regla 5)", "DELETE", "/renos/{{renoId}}", token=JEFE,
        tests=espera(409, "RENO_ASIGNADO_NO_ELIMINABLE")),
    req("Registrar reno con poca energía - 201", "POST", "/renos", token=JEFE,
        body={"nombre": "Debil-{{$timestamp}}", "edad": 3, "nivelEnergia": 40},
        tests=espera(201) + ["pm.collectionVariables.set('renoDebilId', pm.response.json().id);"]),
    req("Asignar con energía < 70 - 409 (regla 1)", "PATCH", "/renos/{{renoDebilId}}/asignacion", token=JEFE,
        tests=espera(409, "ENERGIA_INSUFICIENTE")),
    req("Eliminar reno disponible - 204", "DELETE", "/renos/{{renoDebilId}}", token=JEFE,
        tests=espera(204) + ["pm.test('sin cuerpo', () => pm.expect(pm.response.text()).to.eql(''));"]),
]

mantenimientos = [
    req("Programar en ESTABLO - 201", "POST", "/mantenimientos", body=MANT,
        pre=js("const d = new Date(Date.now() + 86400000);",
               "pm.collectionVariables.set('fechaManana', d.toISOString().slice(0, 10));"),
        tests=espera(201) + [
            "const b = pm.response.json();",
            "pm.test('estado PROGRAMADO', () => pm.expect(b.estado).to.eql('PROGRAMADO'));",
            "pm.collectionVariables.set('mantId', b.id);",
        ]),
    req("Listar por zona - 200", "GET", "/mantenimientos?zona=ESTABLO", tests=espera(200) + [
        "pm.test('todos en ESTABLO', () => pm.response.json().forEach(m => pm.expect(m.zona).to.eql('ESTABLO')));",
    ]),
    req("Fecha pasada - 400", "POST", "/mantenimientos", body={**MANT, "fechaProgramada": "2020-01-01"},
        tests=espera(400, "VALIDACION")),
    req("JSON mal formado - 400", "POST", "/mantenimientos", body=None, tests=espera(400, "JSON_INVALIDO")),
    req("Transición PROGRAMADO -> COMPLETADO - 409", "PATCH", "/mantenimientos/{{mantId}}/estado",
        body={"estado": "COMPLETADO"}, tests=espera(409, "TRANSICION_INVALIDA")),
    req("Transición PROGRAMADO -> EN_CURSO - 200", "PATCH", "/mantenimientos/{{mantId}}/estado",
        body={"estado": "EN_CURSO"}, tests=espera(200)),
    req("Transición EN_CURSO -> COMPLETADO - 200", "PATCH", "/mantenimientos/{{mantId}}/estado",
        body={"estado": "COMPLETADO"}, tests=espera(200) + [
            "pm.test('COMPLETADO', () => pm.expect(pm.response.json().estado).to.eql('COMPLETADO'));"]),
    req("Mantenimiento inexistente - 404", "PATCH", "/mantenimientos/999999/estado", body={"estado": "EN_CURSO"},
        tests=espera(404, "MANTENIMIENTO_NO_ENCONTRADO")),
    req("PISTA_DESPEGUE con clima OK - 201 (consulta SOAP)", "POST", "/mantenimientos",
        body={**MANT, "zona": "PISTA_DESPEGUE", "tipo": "LIMPIEZA_NIEVE", "fechaProgramada": "{{fechaDespejada}}"},
        tests=espera(201) + [
            "pm.test('trae el pronóstico', () => pm.expect(pm.response.json().pronostico).to.be.oneOf(['DESPEJADO','NEVADA_LEVE']));"]),
    req("PISTA_DESPEGUE con VENTISCA - 422 (regla 4)", "POST", "/mantenimientos",
        body={**MANT, "zona": "PISTA_DESPEGUE", "tipo": "LIMPIEZA_NIEVE", "fechaProgramada": "{{fechaVentisca}}"},
        tests=espera(422, "PRONOSTICO_VENTISCA")),
    req("SOAP caído (Fault 2026-12-24) - 202 PENDIENTE_CLIMA", "POST", "/mantenimientos",
        body={**MANT, "zona": "PISTA_DESPEGUE", "tipo": "LIMPIEZA_NIEVE", "fechaProgramada": "{{fechaFault}}"},
        tests=espera(202) + [
            "const b = pm.response.json();",
            "pm.test('se guardó PENDIENTE_CLIMA', () => pm.expect(b.mantenimiento.estado).to.eql('PENDIENTE_CLIMA'));",
            "pm.test('explica el motivo', () => pm.expect(b.motivo).to.be.a('string'));",
        ]),
]
# "JSON mal formado" necesita un cuerpo roto, que json.dumps no puede generar
mantenimientos[3]["request"]["header"] = [{"key": "Content-Type", "value": "application/json"}]
mantenimientos[3]["request"]["body"] = {"mode": "raw", "raw": "{ \"zona\": \"ESTABLO\", ", "options": {"raw": {"language": "json"}}}

extra = [
    req("Resumen del vuelo - 200", "GET", "/vuelo/resumen", tests=espera(200) + [
        "const b = pm.response.json();",
        "pm.test('campos del resumen', () => pm.expect(b).to.include.keys('totalAsignados','energiaPromedio','vueloListo'));",
    ]),
    req("Limpieza: liberar el reno asignado - 200", "PUT", "/renos/{{renoId}}", token=JEFE,
        body={"nombre": "{{renoNombre}}", "edad": 6, "nivelEnergia": 95, "estado": "DISPONIBLE"},
        desc="Deja la base como estaba para poder volver a correr la colección sin llenar el cupo de 9.",
        tests=espera(200)),
    req("Limpieza: eliminar el reno - 204", "DELETE", "/renos/{{renoId}}", token=JEFE, tests=espera(204)),
]

FORMATO_ERROR = [
    "// Para TODA respuesta de error: formato único { codigo, mensaje, detalles, timestamp, ruta }",
    "if (pm.response.code >= 400) {",
    "  pm.test('Formato de error estándar', () => {",
    "    const b = pm.response.json();",
    "    pm.expect(b).to.have.all.keys('codigo', 'mensaje', 'detalles', 'timestamp', 'ruta');",
    "    pm.expect(b.detalles).to.be.an('array');",
    "  });",
    "}",
]

coleccion = {
    "info": {
        "name": "Polo Norte API (FastAPI) - Escenario B (Establo de renos)",
        "description": "Ejecutar en orden con Run collection. Los logins guardan tokenJefe y tokenElfo; "
                       "las creaciones guardan renoId, renoDebilId y mantId. Al final se limpia lo creado.",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": FORMATO_ERROR}}],
    "variable": [{"key": k, "value": v} for k, v in {
        "baseUrl": "http://127.0.0.1:8000/api",
        "jefeUser": "jefe", "jefePassword": "jefe123",
        "elfoUser": "elfo", "elfoPassword": "elfo123",
        "fechaDespejada": "2026-12-19", "fechaVentisca": "2026-12-21", "fechaFault": "2026-12-24",
        "tokenJefe": "", "tokenElfo": "", "renoId": "", "renoDebilId": "", "renoNombre": "", "mantId": "",
        "fechaManana": "",
    }.items()],
    "item": [
        {"name": "0. Auth", "item": auth},
        {"name": "1. Renos", "item": renos},
        {"name": "2. Mantenimientos", "item": mantenimientos},
        {"name": "3. Extra y limpieza", "item": extra},
    ],
}

SALIDA.parent.mkdir(exist_ok=True)
SALIDA.write_text(json.dumps(coleccion, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"OK: {SALIDA} ({sum(len(c['item']) for c in coleccion['item'])} requests)")
