"""
Adaptador del servicio SOAP heredado MeteoPoloNorteService.
Es el ÚNICO lugar del sistema que conoce XML/SOAP: recibe parámetros de dominio
y devuelve un objeto de dominio {"zona", "fecha", "condicion"}.

Fallos (timeout de 3 s, error de red, soap:Fault, respuesta inválida) se traducen a
ServicioExternoNoDisponibleError tras reintentar con backoff exponencial (máx. 2 intentos).
"""
import time
from xml.etree.ElementTree import Element
from xml.sax.saxutils import escape

import httpx
from defusedxml import ElementTree as SafeET  # evita XXE y "billion laughs"

from ..config import env, env_int

CONDICIONES = ["DESPEJADO", "NEVADA_LEVE", "VENTISCA"]


class ServicioExternoNoDisponibleError(Exception):
    """Error de dominio: el servicio meteorológico no respondió. No contiene nada de XML."""

    def __init__(self, motivo: str, intentos: int):
        super().__init__(motivo)
        self.motivo = motivo
        self.intentos = intentos


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]  # "{http://...}Body" -> "Body"


def _hijo(el: Element | None, nombre: str) -> Element | None:
    if el is None:
        return None
    return next((h for h in el if _local(h.tag) == nombre), None)


def _texto(el: Element | None, nombre: str) -> str | None:
    h = _hijo(el, nombre)
    return h.text.strip() if h is not None and h.text else None


class MeteoAdapter:
    def __init__(self, url=None, timeout_ms=None, intentos=None, backoff_ms=None, soap_action=None):
        self._opciones = {"url": url, "timeout_ms": timeout_ms, "intentos": intentos,
                          "backoff_ms": backoff_ms, "soap_action": soap_action}

    @property
    def config(self) -> dict:
        """Se lee en cada llamada (permite cambiar .env o los tests sin reiniciar)."""
        o = self._opciones
        return {
            "url": o["url"] or env("METEO_URL", "http://127.0.0.1:8089/meteo"),
            "timeout_ms": o["timeout_ms"] or env_int("METEO_TIMEOUT_MS", 3000),
            "intentos": o["intentos"] or env_int("METEO_MAX_INTENTOS", 2),
            "backoff_ms": o["backoff_ms"] if o["backoff_ms"] is not None else env_int("METEO_BACKOFF_MS", 300),
            "soap_action": o["soap_action"] or env("METEO_SOAP_ACTION", "ObtenerPronostico"),
        }

    # --- dominio -> XML -------------------------------------------------------
    def construir_request(self, zona: str, fecha: str) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:mt="http://polonorte.beatiech/meteo">
  <soapenv:Body>
    <mt:ObtenerPronosticoRequest>
      <mt:zona>{escape(zona)}</mt:zona>
      <mt:fecha>{escape(fecha)}</mt:fecha>
    </mt:ObtenerPronosticoRequest>
  </soapenv:Body>
</soapenv:Envelope>"""

    # --- XML -> dominio (o excepción si es Fault / inválido) -------------------
    def parsear_respuesta(self, xml: str, zona: str, fecha: str) -> dict:
        try:
            raiz = SafeET.fromstring(xml)
        except Exception:  # noqa: BLE001 - cualquier XML roto es "respuesta inválida"
            raise ValueError("respuesta XML inválida") from None
        body = _hijo(raiz, "Body") if _local(raiz.tag) == "Envelope" else None
        if body is None:
            raise ValueError("respuesta sin soap:Body")

        fault = _hijo(body, "Fault")
        if fault is not None:
            raise ValueError(f"{_texto(fault, 'faultcode')}: {_texto(fault, 'faultstring')}")

        condicion = _texto(_hijo(body, "ObtenerPronosticoResponse"), "pronostico")
        if condicion not in CONDICIONES:
            raise ValueError(f"pronóstico desconocido: {condicion}")
        return {"zona": zona, "fecha": fecha, "condicion": condicion}

    def llamar_una_vez(self, zona: str, fecha: str) -> dict:
        c = self.config
        try:
            res = httpx.post(
                c["url"],
                content=self.construir_request(zona, fecha).encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": c["soap_action"]},
                timeout=c["timeout_ms"] / 1000,
            )
        except httpx.ConnectTimeout:
            raise ValueError(f"no se pudo conectar en {c['timeout_ms']} ms") from None
        except httpx.TimeoutException:
            raise ValueError(f"sin respuesta en {c['timeout_ms']} ms") from None
        except httpx.HTTPError as err:
            raise ValueError(f"error de red ({type(err).__name__})") from None
        # El Fault llega con HTTP 500: lo analizamos nosotros, no por el código HTTP
        return self.parsear_respuesta(res.text, zona, fecha)

    # --- API pública del adaptador ------------------------------------------------
    def obtener_pronostico(self, zona: str, fecha: str) -> dict:
        c = self.config
        ultimo_error = None
        for intento in range(1, c["intentos"] + 1):
            try:
                return self.llamar_una_vez(zona, fecha)
            except ValueError as err:
                ultimo_error = err
                if intento < c["intentos"]:
                    time.sleep(c["backoff_ms"] * 2 ** (intento - 1) / 1000)  # backoff exponencial
        raise ServicioExternoNoDisponibleError(str(ultimo_error), c["intentos"])


_adaptador = MeteoAdapter()


def get_meteo_adapter() -> MeteoAdapter:
    """Dependencia de FastAPI (los tests la reemplazan con dependency_overrides)."""
    return _adaptador
