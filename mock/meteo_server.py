"""
Mock LOCAL del servicio SOAP MeteoPoloNorteService (para desarrollo; en el examen usa el del docente).
Respuesta según la fecha solicitada:
  2026-12-24        -> soap:Fault "Estación sin señal" (igual que el mock del docente)
  2026-12-23        -> tarda 5 s (provoca el timeout de 3 s)
  día múltiplo de 3 -> VENTISCA      (ej. 2026-12-21)
  día par           -> NEVADA_LEVE   (ej. 2026-12-20)
  resto             -> DESPEJADO     (ej. 2026-12-19)
METEO_MOCK_DELAY_MS agrega un retraso a todas las respuestas.

Uso:  python -m mock.meteo_server     (escucha en http://127.0.0.1:8089/meteo)
"""
import asyncio
import os
from xml.sax.saxutils import escape

from defusedxml import ElementTree as SafeET
from fastapi import FastAPI, Request, Response

app = FastAPI(title="Mock MeteoPoloNorteService")


def _envelope(body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:mt="http://polonorte.beatiech/meteo">
  <soapenv:Body>{body}</soapenv:Body>
</soapenv:Envelope>"""


def _fault(mensaje: str) -> str:
    return _envelope(f"""
    <soapenv:Fault>
      <faultcode>soap:Server</faultcode>
      <faultstring>{escape(mensaje)}</faultstring>
    </soapenv:Fault>""")


def pronostico_para(fecha: str) -> str | None:
    if fecha == "2026-12-24":
        return None
    dia = int(fecha[8:10])
    if dia % 3 == 0:
        return "VENTISCA"
    if dia % 2 == 0:
        return "NEVADA_LEVE"
    return "DESPEJADO"


def _leer_request(xml: bytes) -> tuple[str | None, str | None]:
    try:
        raiz = SafeET.fromstring(xml)
    except Exception:  # noqa: BLE001
        return None, None
    valores = {el.tag.rsplit("}", 1)[-1]: (el.text or "").strip() for el in raiz.iter()}
    return valores.get("zona") or None, valores.get("fecha") or None


@app.post("/meteo")
async def meteo(request: Request):
    zona, fecha = _leer_request(await request.body())

    retraso = int(os.getenv("METEO_MOCK_DELAY_MS", "0")) + (5000 if fecha == "2026-12-23" else 0)
    if retraso:
        await asyncio.sleep(retraso / 1000)

    if not zona or not fecha or len(fecha) != 10 or not fecha[8:10].isdigit():
        return Response(_fault("Request inválido"), status_code=500, media_type="text/xml")

    p = pronostico_para(fecha)
    if p is None:
        return Response(_fault("Estación sin señal"), status_code=500, media_type="text/xml")
    return Response(_envelope(f"""
    <mt:ObtenerPronosticoResponse>
      <mt:pronostico>{p}</mt:pronostico>
    </mt:ObtenerPronosticoResponse>"""), media_type="text/xml")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("METEO_MOCK_PORT", "8089")))
