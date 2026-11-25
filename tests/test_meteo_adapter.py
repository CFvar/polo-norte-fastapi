"""Adaptador SOAP contra el mock real (HTTP de verdad): éxito, Fault, timeout y servicio apagado."""
import socket
import threading
import time

import pytest
import uvicorn

from app.adapters.meteo_adapter import MeteoAdapter, ServicioExternoNoDisponibleError
from mock.meteo_server import app as mock_app


@pytest.fixture(scope="module")
def url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(mock_app, host="127.0.0.1", port=puerto, log_level="warning"))
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{puerto}/meteo"
    server.should_exit = True
    hilo.join(timeout=5)


@pytest.fixture
def adapter(url):
    return lambda **o: MeteoAdapter(**{"url": url, "timeout_ms": 1000, "backoff_ms": 10, **o})


@pytest.mark.parametrize("fecha,condicion", [
    ("2030-12-19", "DESPEJADO"), ("2030-12-20", "NEVADA_LEVE"), ("2030-12-21", "VENTISCA"),
])
def test_xml_a_objeto_de_dominio(adapter, fecha, condicion):
    assert adapter().obtener_pronostico("PISTA_DESPEGUE", fecha) == {
        "zona": "PISTA_DESPEGUE", "fecha": fecha, "condicion": condicion}


def test_fault_reintenta_y_lanza_error_de_dominio(adapter, monkeypatch):
    a = adapter()
    llamadas = []
    original = a.llamar_una_vez
    monkeypatch.setattr(a, "llamar_una_vez", lambda z, f: llamadas.append(1) or original(z, f))
    with pytest.raises(ServicioExternoNoDisponibleError) as exc:
        a.obtener_pronostico("PISTA_DESPEGUE", "2026-12-24")
    assert "Estación sin señal" in exc.value.motivo
    assert exc.value.intentos == 2 and len(llamadas) == 2


def test_timeout(adapter, monkeypatch):
    monkeypatch.setenv("METEO_MOCK_DELAY_MS", "400")
    with pytest.raises(ServicioExternoNoDisponibleError) as exc:
        adapter(timeout_ms=150).obtener_pronostico("PISTA_DESPEGUE", "2030-12-19")
    assert "sin respuesta en 150 ms" in exc.value.motivo


def test_servicio_apagado(adapter):
    with pytest.raises(ServicioExternoNoDisponibleError) as exc:
        adapter(url="http://127.0.0.1:1/meteo").obtener_pronostico("PISTA_DESPEGUE", "2030-12-19")
    # Linux rechaza la conexión al instante; Windows suele agotar el timeout de conexión
    assert "error de red" in exc.value.motivo or "no se pudo conectar" in exc.value.motivo


def test_respuesta_no_xml():
    with pytest.raises(ValueError, match="XML inválida"):
        MeteoAdapter().parsear_respuesta("<html>oops", "PISTA_DESPEGUE", "2030-12-19")


def test_construye_envelope_y_escapa_xml(adapter):
    xml = adapter().construir_request("PISTA_DESPEGUE", "2026-12-20")
    assert "<mt:zona>PISTA_DESPEGUE</mt:zona>" in xml and "<mt:fecha>2026-12-20</mt:fecha>" in xml
    assert "<mt:zona>a&lt;b&amp;c</mt:zona>" in adapter().construir_request("a<b&c", "x")
